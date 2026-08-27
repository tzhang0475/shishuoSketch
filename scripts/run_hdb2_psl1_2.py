#!/usr/bin/env python3
"""Run HDB2-PSL1.2 candidate rescue as an additive experiment.

The normal PSL1.1 predicate and adversarial-review calls are kept unchanged.
PSL1.2 adds at most one diagnostic call after an open/rejected result.  A
diagnosis can only lead to a Python lookup in already-grounded resources;
the rescue model never selects or creates a Person.
"""

from __future__ import annotations

import argparse
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

import hdb2_psl1_2_common as layer  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
from run_hdb2_psl1 import (  # noqa: E402
    _call_tool,
    preflight,
    protected_hashes,
    usage,
    utc_now,
)


OUT_ROOT = ROOT / "data/generated/hdb2-psl1-2/live"
SELECTION_PATH = layer.SELECTION_PATH


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(raw_dir.glob("*.json"))
    }


def _call_record_failure(record: Mapping[str, Any], failure: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not failure:
        return None
    return {
        "sequence": record.get("sequence"),
        "call_type": record.get("call_type"),
        "mention_id": record.get("mention_id"),
        "story_id": record.get("story_id"),
        "classification": record.get("classification"),
        "errors": list(failure.get("errors", [])),
    }


def _neutral_record(case: Mapping[str, Any], call_type: str, packet_key: str, reason: str) -> dict[str, Any]:
    payload: dict[str, Any]
    if call_type == "predicate_evaluation":
        payload = {"predicates": [], "note": reason}
    elif call_type == "candidate_rescue_diagnosis":
        payload = {}
    else:
        payload = {}
    return {
        "sequence": None,
        "call_type": call_type,
        "packet_key": packet_key,
        "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"),
        "payload": payload,
        "validation": {"valid": call_type == "predicate_evaluation", "errors": [] if call_type == "predicate_evaluation" else [reason]},
        "classification": "not_run_preflight_failure",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _valid_predicates(model_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in model_records:
        if row.get("call_type") != "predicate_evaluation" or (row.get("validation") or {}).get("valid") is not True:
            continue
        for predicate in (row.get("payload") or {}).get("predicates", []) or []:
            result.append({"mention_id": row.get("mention_id"), **dict(predicate)})
    return result


def _state_counts(document: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in document.get("records", []) or []:
        state = str(row.get("result_state") or "")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def _packet_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for filename in ("prompt-packets.json", "reviewer-packets.json", "rescue-packets.json"):
        document = layer.read_json(run_dir / filename, {}) or {}
        for row in document.get("records", []) or []:
            if row.get("key"):
                result[str(row.get("key"))] = row.get("packet") or {}
    return result


def _write_packets(run_dir: Path, packets: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    for filename, key in (
        ("prompt-packets.json", "contextual"),
        ("reviewer-packets.json", "reviewer"),
        ("rescue-packets.json", "rescue"),
    ):
        layer.write_json(run_dir / filename, {
            "records": list(packets.get(key, [])),
            "candidate_only": True,
            "canonical_write_back": False,
        })


def _review_targets(
    graph: Mapping[str, Any],
    decisions: Mapping[str, Any],
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    cases = {str(case.get("mention_id")): case for case in graph.get("cases", [])}
    result: list[dict[str, Any]] = []
    for decision in decisions.get("records", []) or []:
        allowed_states = {"stable_entity_resolved", "review_required"}
        # A grounded rescue can introduce a local candidate.  The frozen
        # PSL1.1 path does not review such states in its first pass, but a
        # rescue rerun must still pass the new candidate through the same
        # adversarial reviewer before it can be retained as a resolution.
        if prefix == "rescue":
            allowed_states.add("local_candidate_resolved")
        if str(decision.get("result_state")) not in allowed_states:
            continue
        case = cases.get(str(decision.get("mention_id")))
        if not case:
            continue
        result.append({
            "key": f"review:{prefix}:{case.get('mention_id')}",
            "packet": layer.psl1_1.reviewer_packet(case, graph.get("cases", []), graph, decision),
            "mention_id": case.get("mention_id"),
            "prefix": prefix,
        })
    return result


def _apply_review_rows(
    decisions: Mapping[str, Any],
    reviewer_rows: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
) -> dict[str, Any]:
    return layer.psl1_1.apply_reviewer(decisions, reviewer_rows, graph)


def _run_calls(
    *,
    run_dir: Path,
    graph: Mapping[str, Any],
    preflight_record: Mapping[str, Any],
    packets: dict[str, list[dict[str, Any]]],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Run the frozen contextual/reviewer calls for the selected graph."""
    if preflight_record.get("status") != "reachable":
        for case in graph.get("cases", []) or []:
            key = f"contextual:{case.get('mention_id')}"
            packet = layer.psl1_1.wire_packet(case, graph.get("cases", []), graph)
            packets["contextual"].append({"key": key, "packet": packet, "sent_to_provider": False})
            model_records.append(_neutral_record(case, "predicate_evaluation", key, "preflight_unavailable"))
        return [], [], [], sequence

    predicate_records: list[dict[str, Any]] = []
    for case in graph.get("cases", []) or []:
        packet = layer.psl1_1.wire_packet(case, graph.get("cases", []), graph)
        key = f"contextual:{case.get('mention_id')}"
        packets["contextual"].append({"key": key, "packet": packet, "sent_to_provider": bool(packet.get("request_predicates"))})
        if not packet.get("request_predicates"):
            row = _neutral_record(case, "predicate_evaluation", key, "no_requested_llm_predicates")
            row["classification"] = "no_call"
            row["packet_key"] = key
            model_records.append(row)
            predicate_records.append(row)
            continue
        sequence += 1
        call_record, model_record, failure = _call_tool(
            packet=packet,
            sequence=sequence,
            call_type="predicate_evaluation",
            system_prompt=psl1.SYSTEM_PROMPT,
            tool=psl1.predicate_tool(),
            choice=psl1.tool_choice(),
            expected_function=psl1.FUNCTION_NAME,
            prompt_version=psl1.PROMPT_VERSION,
            raw_dir=run_dir / "raw-api",
            validator=psl1.validate_predicates,
        )
        call_record.update({"packet_key": key, "stage": "initial"})
        model_record.update({"packet_key": key, "stage": "initial"})
        call_records.append(call_record)
        model_records.append(model_record)
        predicate_records.append(model_record)
        failure_row = _call_record_failure(call_record, failure)
        if failure_row:
            failures.append(failure_row)

    initial = layer.psl1_1.infer_graph(graph, _valid_predicates(predicate_records))
    reviewer_packets = _review_targets(graph, initial, prefix="initial")
    packets["reviewer"].extend(reviewer_packets)
    reviewer_records: list[dict[str, Any]] = []
    for packet_row in reviewer_packets:
        case = next(case for case in graph.get("cases", []) if str(case.get("mention_id")) == str(packet_row.get("mention_id")))
        sequence += 1
        call_record, model_record, failure = _call_tool(
            packet=packet_row["packet"],
            sequence=sequence,
            call_type="adversarial_review",
            system_prompt=psl1.REVIEW_SYSTEM_PROMPT,
            tool=psl1.reviewer_tool(),
            choice=psl1.reviewer_tool_choice(),
            expected_function=psl1.REVIEW_FUNCTION_NAME,
            prompt_version=psl1.REVIEW_PROMPT_VERSION,
            raw_dir=run_dir / "raw-api",
            validator=psl1.validate_reviewer,
        )
        call_record.update({"packet_key": packet_row["key"], "stage": "initial"})
        model_record.update({"packet_key": packet_row["key"], "stage": "initial"})
        call_records.append(call_record)
        model_records.append(model_record)
        reviewer_records.append(model_record)
        failure_row = _call_record_failure(call_record, failure)
        if failure_row:
            failures.append(failure_row)
    return predicate_records, reviewer_records, [initial], sequence


def _diagnostic_calls(
    *,
    run_dir: Path,
    graph: Mapping[str, Any],
    after_review: Mapping[str, Any],
    packets: dict[str, list[dict[str, Any]]],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
    preflight_record: Mapping[str, Any],
    reviewer_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], int]:
    cases = {str(case.get("mention_id")): case for case in graph.get("cases", []) or []}
    reviewer_by_mention = {
        str(row.get("mention_id")): row
        for row in reviewer_rows
        if row.get("mention_id")
    }
    rows: list[dict[str, Any]] = []
    for decision in after_review.get("records", []) or []:
        if not layer.rescue_trigger(decision):
            continue
        case = cases.get(str(decision.get("mention_id")))
        if not case:
            continue
        packet = layer.rescue_packet(
            case,
            decision,
            graph,
            reviewer_by_mention.get(str(decision.get("mention_id"))),
        )
        key = f"rescue:{case.get('mention_id')}"
        packets["rescue"].append({"key": key, "packet": packet, "sent_to_provider": preflight_record.get("status") == "reachable"})
        if preflight_record.get("status") != "reachable":
            row = _neutral_record(case, "candidate_rescue_diagnosis", key, "preflight_unavailable")
            row["stage"] = "rescue"
            row["packet_key"] = key
            model_records.append(row)
            rows.append(row)
            continue
        sequence += 1
        call_record, model_record, failure = _call_tool(
            packet=packet,
            sequence=sequence,
            call_type="candidate_rescue_diagnosis",
            system_prompt=layer.RESCUE_SYSTEM_PROMPT,
            tool=layer.rescue_tool(),
            choice=layer.rescue_tool_choice(),
            expected_function=layer.RESCUE_FUNCTION_NAME,
            prompt_version=layer.PROMPT_VERSION,
            raw_dir=run_dir / "raw-api",
            validator=layer.validate_rescue_diagnosis,
        )
        call_record.update({"packet_key": key, "stage": "rescue"})
        model_record.update({"packet_key": key, "stage": "rescue"})
        call_records.append(call_record)
        model_records.append(model_record)
        rows.append(model_record)
        failure_row = _call_record_failure(call_record, failure)
        if failure_row:
            failures.append(failure_row)
    return rows, sequence


def _add_grounded_candidates(
    graph: Mapping[str, Any],
    rescue_records: Sequence[Mapping[str, Any]],
    resources: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    result = json.loads(json.dumps(graph, ensure_ascii=False))
    diagnoses: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    cases = {str(case.get("mention_id")): case for case in result.get("cases", []) or []}
    for record in rescue_records:
        validation = record.get("validation") or {}
        payload = record.get("payload") or {}
        row = {
            "mention_id": record.get("mention_id"),
            "occurrence_id": cases.get(str(record.get("mention_id")), {}).get("occurrence_id"),
            "diagnosis": payload.get("diagnosis"),
            "proposed_identity_surface": payload.get("proposed_identity_surface"),
            "reference_type": payload.get("reference_type"),
            "search_hints": list(payload.get("search_hints", []) or []) if isinstance(payload, Mapping) else [],
            "supporting_evidence_ids": list(payload.get("supporting_evidence_ids", []) or []) if isinstance(payload, Mapping) else [],
            "validation": {"valid": validation.get("valid"), "errors": list(validation.get("errors", []))},
        }
        diagnoses.append(row)
        if validation.get("valid") is not True or payload.get("diagnosis") != "candidate_missing_likely":
            continue
        case = cases.get(str(record.get("mention_id")))
        if not case:
            continue
        grounded = layer.find_grounded_rescue_candidates(case, payload, resources)
        if grounded.get("candidates"):
            updated, additions = layer.add_rescue_candidates(result, str(case.get("occurrence_id")), grounded)
            result = updated
            provenance.extend(additions)
    return result, diagnoses, provenance


def _rerun_after_rescue(
    *,
    graph: Mapping[str, Any],
    original_predicates: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    packets: dict[str, list[dict[str, Any]]],
    run_dir: Path,
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
    preflight_record: Mapping[str, Any],
    saved_reviewer_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    rescue_graph = graph
    rescue_rows = layer.rescue_predicates(rescue_graph, provenance)
    final_initial = layer.psl1_1.infer_graph(rescue_graph, [*original_predicates, *rescue_rows])
    rescued_ids = {str(row.get("occurrence_id")) for row in provenance}
    reviewer_rows: list[dict[str, Any]] = []
    if saved_reviewer_rows and rescued_ids:
        # Offline replay applies the immutable rescue-review records captured
        # by the live run.  It must not call the provider again, while still
        # reproducing the live post-rescue state transition.
        eligible_mentions = {
            str(case.get("mention_id"))
            for case in rescue_graph.get("cases", [])
            if str(case.get("occurrence_id")) in rescued_ids
        }
        reviewer_rows.extend(
            dict(row)
            for row in saved_reviewer_rows
            if str(row.get("mention_id")) in eligible_mentions
            and (row.get("validation") or {}).get("valid") is True
        )
    elif preflight_record.get("status") == "reachable" and rescued_ids:
        for packet_row in _review_targets(rescue_graph, final_initial, prefix="rescue"):
            if str(packet_row.get("mention_id")) not in {
                str(case.get("mention_id")) for case in rescue_graph.get("cases", [])
                if str(case.get("occurrence_id")) in rescued_ids
            }:
                continue
            packets["reviewer"].append(packet_row)
            case = next(case for case in rescue_graph.get("cases", []) if str(case.get("mention_id")) == str(packet_row.get("mention_id")))
            sequence += 1
            call_record, model_record, failure = _call_tool(
                packet=packet_row["packet"],
                sequence=sequence,
                call_type="adversarial_review",
                system_prompt=psl1.REVIEW_SYSTEM_PROMPT,
                tool=psl1.reviewer_tool(),
                choice=psl1.reviewer_tool_choice(),
                expected_function=psl1.REVIEW_FUNCTION_NAME,
                prompt_version=psl1.REVIEW_PROMPT_VERSION,
                raw_dir=run_dir / "raw-api",
                validator=psl1.validate_reviewer,
            )
            call_record.update({"packet_key": packet_row["key"], "stage": "rescue"})
            model_record.update({"packet_key": packet_row["key"], "stage": "rescue"})
            call_records.append(call_record)
            model_records.append(model_record)
            reviewer_rows.append(model_record)
            failure_row = _call_record_failure(call_record, failure)
            if failure_row:
                failures.append(failure_row)
    rescued_final = layer.psl1_1.apply_reviewer(final_initial, reviewer_rows, rescue_graph)
    # Keep the first reviewer decision for cases that did not receive a new
    # candidate; only rescued occurrences get their rerun result.
    return rescued_final, reviewer_rows, sequence


def _merge_final(
    before: Mapping[str, Any],
    rescued: Mapping[str, Any],
    provenance: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rescued_ids = {str(row.get("occurrence_id")) for row in provenance}
    rescued_by_id = {str(row.get("occurrence_id")): row for row in rescued.get("records", []) or []}
    records: list[dict[str, Any]] = []
    for row in before.get("records", []) or []:
        current = dict(row)
        if str(row.get("occurrence_id")) in rescued_ids and str(row.get("occurrence_id")) in rescued_by_id:
            current = dict(rescued_by_id[str(row.get("occurrence_id"))])
        records.append(current)
    return {
        "schema": "hdb2-psl1-2-final-decisions-v1",
        "selection_hash": before.get("selection_hash"),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _rescue_audit(
    *,
    graph: Mapping[str, Any],
    after_review: Mapping[str, Any],
    final: Mapping[str, Any],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a compact, occurrence-level audit of the rescue decision.

    This deliberately keeps the model packet and raw responses out of the
    human audit file.  Candidate identifiers may remain here for audit, but
    the artifact is still explicitly candidate-only and never a materialized
    identity decision.
    """
    cases = {str(case.get("mention_id")): case for case in graph.get("cases", []) or []}
    before = {str(row.get("mention_id")): row for row in after_review.get("records", []) or []}
    after = {str(row.get("mention_id")): row for row in final.get("records", []) or []}
    diagnosis_by = {str(row.get("mention_id")): row for row in diagnoses}
    provenance_by: dict[str, list[dict[str, Any]]] = {}
    for row in provenance:
        provenance_by.setdefault(str(row.get("mention_id") or ""), []).append(dict(row))
    records: list[dict[str, Any]] = []
    for mention_id in sorted(cases):
        case = cases[mention_id]
        old = before.get(mention_id, {})
        new = after.get(mention_id, old)
        candidate_set = [
            {
                "candidate_key": candidate.get("candidate_key"),
                "candidate": candidate.get("candidate"),
                "person_id": candidate.get("candidate_person_id"),
                "candidate_node_id": candidate.get("candidate_node_id"),
            }
            for candidate in old.get("candidate_rankings", []) or []
        ]
        diagnosis = diagnosis_by.get(mention_id)
        records.append({
            "mention_id": mention_id,
            "occurrence_id": case.get("occurrence_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "initial_candidate_set": candidate_set,
            "initial_state": old.get("result_state"),
            "rescue_attempted": diagnosis is not None,
            "rescue_diagnosis": diagnosis,
            "rescued_candidates": provenance_by.get(mention_id, []),
            "final_state": new.get("result_state"),
            "final_candidate": new.get("top_candidate"),
            "final_candidate_person_id": new.get("top_candidate_person_id"),
            "reviewer_verdict": new.get("reviewer_verdict"),
            "rescue_changed_decision": (
                old.get("result_state") != new.get("result_state")
                or old.get("top_candidate") != new.get("top_candidate")
            ),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-2-rescue-audit-v1",
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(
    *,
    selection: Mapping[str, Any],
    graph: Mapping[str, Any],
    initial: Mapping[str, Any],
    after_review: Mapping[str, Any],
    final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    rescue_records: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    resources: Sequence[Mapping[str, Any]],
    preflight_record: Mapping[str, Any],
) -> dict[str, Any]:
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records]
    diagnosis_counts: dict[str, int] = {}
    for row in diagnoses:
        diagnosis = str(row.get("diagnosis") or "invalid_or_missing")
        diagnosis_counts[diagnosis] = diagnosis_counts.get(diagnosis, 0) + 1
    state_changes = []
    initial_by = {str(row.get("occurrence_id")): row for row in after_review.get("records", []) or []}
    for row in final.get("records", []) or []:
        old = initial_by.get(str(row.get("occurrence_id")), {})
        if old.get("result_state") != row.get("result_state") or old.get("top_candidate") != row.get("top_candidate"):
            state_changes.append({
                "occurrence_id": row.get("occurrence_id"),
                "from_state": old.get("result_state"),
                "to_state": row.get("result_state"),
                "from_candidate": old.get("top_candidate"),
                "to_candidate": row.get("top_candidate"),
            })
    # A grounded rescue is successful when Python found an admissible source
    # identity and attached it as a candidate.  ``person_id`` is intentionally
    # absent for source-supported people not yet in the production catalogue;
    # those are still useful candidate rescues, but are reported separately.
    rescue_successes = [row for row in provenance if row.get("direct_identity_support")]
    invalid_rescue_mentions = {
        str(row.get("mention_id"))
        for row in model_records
        if row.get("call_type") == "candidate_rescue_diagnosis"
        and (row.get("validation") or {}).get("valid") is not True
    }
    provenance_mentions = {str(row.get("mention_id") or "") for row in provenance}
    return {
        "schema": "hdb2-psl1-2-metrics-v1",
        "selection_hash": selection.get("selection_hash"),
        "independent_count": len(graph.get("cases", []) or []),
        "initial_states": _state_counts(initial),
        "after_review_states": _state_counts(after_review),
        "final_states": _state_counts(final),
        "rescue_diagnoses": dict(sorted(diagnosis_counts.items())),
        "rescue_attempts": len(rescue_records),
        "valid_rescue_diagnoses": sum((row.get("validation") or {}).get("valid") is True for row in rescue_records),
        "candidate_missing_likely": sum(row.get("diagnosis") == "candidate_missing_likely" for row in diagnoses),
        "grounded_rescue_successes": len(rescue_successes),
        "grounded_rescue_candidates": len(provenance),
        "rescued_existing_persons": len({str(row.get("person_id")) for row in rescue_successes if row.get("person_id")}),
        "resources": len(resources),
        "state_changes_after_rescue": sorted(state_changes, key=lambda row: str(row.get("occurrence_id"))),
        "contextual_calls": sum(row.get("call_type") == "predicate_evaluation" for row in call_records),
        "reviewer_calls": sum(row.get("call_type") == "adversarial_review" for row in call_records),
        "rescue_calls": sum(row.get("call_type") == "candidate_rescue_diagnosis" for row in call_records),
        "semantic_calls": len(call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "invalid_payloads": sum(
            (row.get("validation") or {}).get("valid") is not True
            for row in model_records
            if row.get("classification") not in {"no_call", "not_run_preflight_failure", "frozen_replay"}
        ),
        "validation_failures": len(failures),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "invalid_rescue_payload_mutations": len(invalid_rescue_mentions & provenance_mentions),
        "candidate_only": True,
        "canonical_write_back": False,
        "preflight": dict(preflight_record),
    }


def _finalize(
    *,
    run_dir: Path,
    selection: Mapping[str, Any],
    graph: Mapping[str, Any],
    initial: Mapping[str, Any],
    after_review: Mapping[str, Any],
    final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    rescue_records: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    resources: Sequence[Mapping[str, Any]],
    before_hashes: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_without_api: bool,
    metrics_preflight_record: Mapping[str, Any] | None = None,
) -> Path:
    after_hashes = protected_hashes()
    if dict(before_hashes) != after_hashes:
        raise RuntimeError("hdb2_psl1_2_protected_input_changed")
    metrics = _metrics(
        selection=selection,
        graph=graph,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        rescue_records=rescue_records,
        diagnoses=diagnoses,
        provenance=provenance,
        call_records=call_records,
        failures=failures,
        resources=resources,
        preflight_record=metrics_preflight_record or preflight_record,
    )
    required = layer.required_regression_records()
    false_cases = layer.false_resolution_regression()
    layer.write_json(run_dir / "model-results.json", {"records": list(model_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "call-records.json", {"records": list(call_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "rescue-diagnoses.json", {"records": list(diagnoses), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "rescue-candidates.json", {"records": list(provenance), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "rescue-audit.json", _rescue_audit(
        graph=graph,
        after_review=after_review,
        final=final,
        diagnoses=diagnoses,
        provenance=provenance,
    ))
    layer.write_json(run_dir / "decisions-initial.json", initial)
    layer.write_json(run_dir / "decisions-after-review.json", after_review)
    layer.write_json(run_dir / "decisions-final.json", final)
    layer.write_json(run_dir / "metrics.json", metrics)
    layer.write_json(run_dir / "required-regressions.json", required)
    layer.write_json(run_dir / "false-resolution-regressions.json", false_cases)
    layer.write_json(run_dir / "validation-failures.json", {"records": list(failures), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "resources.json", {"records": list(resources), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-psl1-2-validation-summary-v1",
        "valid": bool(required.get("all_pass") and false_cases.get("all_pass") and not failures and metrics.get("invalid_rescue_payload_mutations") == 0),
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_unchanged": dict(before_hashes) == after_hashes,
        "required_regressions": required,
        "false_resolution_regressions": false_cases,
        "replayed_without_api": replayed_without_api,
    })
    manifest = layer.read_json(run_dir / "manifest.json", {}) or {}
    manifest.update({
        "status": "complete",
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "semantic_calls": len(call_records),
        "protected_hashes_before": dict(before_hashes),
        "protected_hashes_after": after_hashes,
        "raw_api_hashes": _raw_hashes(run_dir / "raw-api"),
        "postprocessing_hash": layer.stable_hash({
            "selection": selection,
            "graph": graph,
            "model_records": list(model_records),
            "initial": initial,
            "after_review": after_review,
            "final": final,
            "provenance": list(provenance),
        }),
    })
    layer.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def _revalidate_model_records(run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packets = _packet_map(run_dir)
    records = list((layer.read_json(run_dir / "model-results.json", {}) or {}).get("records", []))
    failures: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []
    for row in records:
        row = dict(row)
        if row.get("classification") in {"no_call", "not_run_preflight_failure", "frozen_replay"}:
            refreshed.append(row)
            continue
        packet = packets.get(str(row.get("packet_key")))
        if not packet:
            validation = {"valid": False, "errors": ["saved_packet_missing"]}
        elif row.get("call_type") == "candidate_rescue_diagnosis":
            validation = layer.validate_rescue_diagnosis(row.get("payload") or {}, packet)
        elif row.get("call_type") == "adversarial_review":
            validation = psl1.validate_reviewer(row.get("payload") or {}, packet)
        else:
            validation = psl1.validate_predicates(row.get("payload") or {}, packet)
        row["validation"] = validation
        if validation.get("valid") is not True:
            failures.append({
                "mention_id": row.get("mention_id"),
                "call_type": row.get("call_type"),
                "errors": list(validation.get("errors", [])),
            })
        refreshed.append(row)
    return refreshed, failures


def replay(run_dir: Path) -> Path:
    """Rebuild all decisions from frozen packets/model output without API."""
    selection = layer.freeze_selection(SELECTION_PATH)
    saved_selection = layer.read_json(run_dir / "selection.json", {}) or {}
    if saved_selection != selection:
        raise RuntimeError("hdb2_psl1_2_selection_drift_on_replay")
    graph = layer.read_json(run_dir / "graph.json", {}) or layer.build_graph(selection)
    resources = list((layer.read_json(run_dir / "resources.json", {}) or {}).get("records", []))
    if not resources:
        resources = layer.build_grounded_resource_index([str(row.get("surface")) for row in selection.get("independent_cases", [])])
    model_records, failures = _revalidate_model_records(run_dir)
    saved_preflight = layer.read_json(run_dir / "preflight.json", {}) or {}
    predicates = _valid_predicates(model_records)
    initial = layer.psl1_1.infer_graph(graph, predicates)
    reviewers = [row for row in model_records if row.get("call_type") == "adversarial_review" and row.get("stage") == "initial"]
    after_review = layer.psl1_1.apply_reviewer(initial, reviewers, graph)
    rescue_records = [row for row in model_records if row.get("call_type") == "candidate_rescue_diagnosis"]
    rescued_graph, diagnoses, provenance = _add_grounded_candidates(graph, rescue_records, resources)
    rescued_final, _rescue_reviewers, _ = _rerun_after_rescue(
        graph=rescued_graph,
        original_predicates=predicates,
        provenance=provenance,
        packets={"contextual": [], "reviewer": [], "rescue": []},
        run_dir=run_dir,
        model_records=[],
        call_records=[],
        failures=failures,
        sequence=0,
        preflight_record={"status": "unavailable", "replayed": True},
        saved_reviewer_rows=[
            row for row in model_records
            if row.get("call_type") == "adversarial_review" and row.get("stage") == "rescue"
        ],
    )
    final = _merge_final(after_review, rescued_final, provenance)
    before = (layer.read_json(run_dir / "manifest.json", {}) or {}).get("protected_hashes_before") or protected_hashes()
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=rescued_graph,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=list((layer.read_json(run_dir / "call-records.json", {}) or {}).get("records", [])),
        failures=failures,
        rescue_records=rescue_records,
        diagnoses=diagnoses,
        provenance=provenance,
        resources=resources,
        before_hashes=before,
        preflight_record={"status": "unavailable", "replayed": True},
        replayed_without_api=True,
        metrics_preflight_record=saved_preflight,
    )


def run(args: argparse.Namespace) -> Path:
    selection = layer.freeze_selection(SELECTION_PATH)
    graph = layer.build_graph(selection)
    target_surfaces = [str(row.get("surface") or "") for row in selection.get("independent_cases", []) or []]
    resources = layer.build_grounded_resource_index(target_surfaces)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-2"
    run_dir = OUT_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl1_2_run_exists:{run_dir}")
    (run_dir / "raw-api").mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    layer.write_json(run_dir / "selection.json", selection)
    layer.write_json(run_dir / "graph.json", graph)
    layer.write_json(run_dir / "resources.json", {"records": resources, "candidate_only": True, "canonical_write_back": False})
    packets: dict[str, list[dict[str, Any]]] = {"contextual": [], "reviewer": [], "rescue": []}
    _write_packets(run_dir, packets)
    if getattr(args, "offline", False):
        preflight_record = {
            "status": "offline",
            "endpoint": layer.STRICT_ENDPOINT,
            "model": layer.MODEL,
            "reason": "explicit_offline_replay_mode",
        }
    else:
        preflight_record = preflight()
    layer.write_json(run_dir / "preflight.json", preflight_record)
    layer.write_json(run_dir / "manifest.json", {
        "schema": "hdb2-psl1-2-live-manifest-v1",
        "run_id": run_id,
        "run_version": layer.RUN_VERSION,
        "prompt_version": psl1.PROMPT_VERSION,
        "review_prompt_version": psl1.REVIEW_PROMPT_VERSION,
        "rescue_prompt_version": layer.PROMPT_VERSION,
        "model": layer.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": layer.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "independent_count": len(graph.get("cases", []) or []),
        "resource_count": len(resources),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": before,
        "preflight": preflight_record,
        "created_at": utc_now(),
    })
    model_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    predicate_records, reviewer_records, initial_docs, sequence = _run_calls(
        run_dir=run_dir,
        graph=graph,
        preflight_record=preflight_record,
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=0,
    )
    _write_packets(run_dir, packets)
    predicates = _valid_predicates(predicate_records)
    initial = initial_docs[0] if initial_docs else layer.psl1_1.infer_graph(graph, predicates)
    after_review = layer.psl1_1.apply_reviewer(initial, reviewer_records, graph)
    rescue_records, sequence = _diagnostic_calls(
        run_dir=run_dir,
        graph=graph,
        after_review=after_review,
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=sequence,
        preflight_record=preflight_record,
        reviewer_rows=reviewer_records,
    )
    _write_packets(run_dir, packets)
    rescued_graph, diagnoses, provenance = _add_grounded_candidates(graph, rescue_records, resources)
    rescued_final, rescue_reviewers, sequence = _rerun_after_rescue(
        graph=rescued_graph,
        original_predicates=predicates,
        provenance=provenance,
        packets=packets,
        run_dir=run_dir,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=sequence,
        preflight_record=preflight_record,
    )
    _write_packets(run_dir, packets)
    final = _merge_final(after_review, rescued_final, provenance)
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=rescued_graph,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        rescue_records=rescue_records,
        diagnoses=diagnoses,
        provenance=provenance,
        resources=resources,
        before_hashes=before,
        preflight_record=preflight_record,
        replayed_without_api=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--replay", type=Path)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="build a candidate-only no-provider run for deterministic local validation",
    )
    args = parser.parse_args()
    if args.replay:
        run_dir = args.replay if args.replay.is_absolute() else ROOT / args.replay
        result = replay(run_dir)
    else:
        result = run(args)
    print(json.dumps({"run_dir": str(result.relative_to(ROOT)), "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
