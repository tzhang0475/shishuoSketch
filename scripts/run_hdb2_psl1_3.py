#!/usr/bin/env python3
"""Run the additive HDB2-PSL1.3 rescue-interface validation.

The contextual predicate/reviewer path is imported unchanged from PSL1.1.
Only the post-review candidate-rescue diagnostic has a new wire contract;
any resulting candidate is still discovered by deterministic, grounded
Python lookup before the frozen resolver is rerun.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_3_common as layer  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
import hdb2_psl1_1_common as psl1_1  # noqa: E402
from run_hdb2_psl1 import (  # noqa: E402
    _call_tool,
    preflight,
    protected_hashes,
    usage,
    utc_now,
)


OUT_ROOT = ROOT / "data/generated/hdb2-psl1-3/live"


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(raw_dir.glob("*.json"))
    }


def _failure(record: Mapping[str, Any], failure: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not failure:
        return None
    return {
        "sequence": record.get("sequence"),
        "call_type": record.get("call_type"),
        "mention_id": record.get("mention_id"),
        "story_id": record.get("story_id"),
        "errors": list(failure.get("errors", [])),
    }


def _valid_predicates(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in records:
        if row.get("call_type") != "predicate_evaluation":
            continue
        if (row.get("validation") or {}).get("valid") is not True:
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
    only_occurrences: set[str] | None = None,
) -> list[dict[str, Any]]:
    cases = {str(case.get("mention_id")): case for case in graph.get("cases", []) or []}
    result: list[dict[str, Any]] = []
    for decision in decisions.get("records", []) or []:
        state = str(decision.get("result_state") or "")
        allowed = {"stable_entity_resolved", "review_required"}
        if prefix == "rescue":
            allowed.add("local_candidate_resolved")
        if state not in allowed:
            continue
        case = cases.get(str(decision.get("mention_id")))
        if not case:
            continue
        if only_occurrences is not None and str(case.get("occurrence_id")) not in only_occurrences:
            continue
        result.append({
            "key": f"review:{prefix}:{case.get('mention_id')}",
            "packet": layer.reviewer_packet(case, graph.get("cases", []), graph, decision),
            "mention_id": case.get("mention_id"),
            "prefix": prefix,
        })
    return result


def _call_stage(
    *,
    run_dir: Path,
    packet: Mapping[str, Any],
    call_type: str,
    system_prompt: str,
    tool: Mapping[str, Any],
    choice: Mapping[str, Any],
    expected_function: str,
    prompt_version: str,
    sequence: int,
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    stage: str,
) -> dict[str, Any]:
    call_record, model_record, failure = _call_tool(
        packet=packet,
        sequence=sequence,
        call_type=call_type,
        system_prompt=system_prompt,
        tool=tool,
        choice=choice,
        expected_function=expected_function,
        prompt_version=prompt_version,
        raw_dir=run_dir / "raw-api",
        validator=(
            layer.validate_rescue_interface
            if call_type == "candidate_rescue_interface"
            else psl1.validate_reviewer
            if call_type == "adversarial_review"
            else psl1.validate_predicates
        ),
    )
    call_record.update({"stage": stage})
    model_record.update({"stage": stage})
    call_records.append(call_record)
    model_records.append(model_record)
    failure_row = _failure(call_record, failure)
    if failure_row:
        failures.append(failure_row)
    return model_record


def _run_initial_calls(
    *,
    run_dir: Path,
    graph: Mapping[str, Any],
    reachable: bool,
    packets: dict[str, list[dict[str, Any]]],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    predicate_records: list[dict[str, Any]] = []
    for case in graph.get("cases", []) or []:
        packet = layer.wire_packet(case, graph.get("cases", []), graph)
        key = f"contextual:{case.get('mention_id')}"
        packets["contextual"].append({"key": key, "packet": packet, "sent_to_provider": bool(reachable and packet.get("request_predicates"))})
        if not reachable or not packet.get("request_predicates"):
            continue
        sequence += 1
        row = _call_stage(
            run_dir=run_dir,
            packet=packet,
            call_type="predicate_evaluation",
            system_prompt=psl1.SYSTEM_PROMPT,
            tool=psl1.predicate_tool(),
            choice=psl1.tool_choice(),
            expected_function=psl1.FUNCTION_NAME,
            prompt_version=psl1.PROMPT_VERSION,
            sequence=sequence,
            model_records=model_records,
            call_records=call_records,
            failures=failures,
            stage="initial",
        )
        row["packet_key"] = key
        call_records[-1]["packet_key"] = key
        predicate_records.append(row)
    initial = psl1_1.infer_graph(graph, _valid_predicates(predicate_records))
    reviewers = _review_targets(graph, initial, prefix="initial") if reachable else []
    packets["reviewer"].extend(reviewers)
    reviewer_records: list[dict[str, Any]] = []
    for item in reviewers:
        sequence += 1
        row = _call_stage(
            run_dir=run_dir,
            packet=item["packet"],
            call_type="adversarial_review",
            system_prompt=psl1.REVIEW_SYSTEM_PROMPT,
            tool=psl1.reviewer_tool(),
            choice=psl1.reviewer_tool_choice(),
            expected_function=psl1.REVIEW_FUNCTION_NAME,
            prompt_version=psl1.REVIEW_PROMPT_VERSION,
            sequence=sequence,
            model_records=model_records,
            call_records=call_records,
            failures=failures,
            stage="initial",
        )
        row["packet_key"] = item["key"]
        call_records[-1]["packet_key"] = item["key"]
        reviewer_records.append(row)
    after_review = psl1_1.apply_reviewer(initial, reviewer_records, graph)
    return initial, after_review, sequence


def _run_rescue_calls(
    *,
    run_dir: Path,
    graph: Mapping[str, Any],
    after_review: Mapping[str, Any],
    reachable: bool,
    packets: dict[str, list[dict[str, Any]]],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
) -> tuple[list[dict[str, Any]], int]:
    cases = {str(case.get("mention_id")): case for case in graph.get("cases", []) or []}
    reviewer_rows = [row for row in model_records if row.get("call_type") == "adversarial_review" and row.get("stage") == "initial"]
    reviewer_by_id = {str(row.get("mention_id")): row for row in reviewer_rows}
    results: list[dict[str, Any]] = []
    for decision in after_review.get("records", []) or []:
        if not layer.rescue_trigger(decision):
            continue
        case = cases.get(str(decision.get("mention_id")))
        if not case:
            continue
        packet = layer.rescue_packet(case, decision, graph, reviewer_by_id.get(str(decision.get("mention_id"))))
        key = f"rescue:{case.get('mention_id')}"
        packets["rescue"].append({"key": key, "packet": packet, "sent_to_provider": bool(reachable)})
        if not reachable:
            continue
        sequence += 1
        row = _call_stage(
            run_dir=run_dir,
            packet=packet,
            call_type="candidate_rescue_interface",
            system_prompt=layer.RESCUE_SYSTEM_PROMPT,
            tool=layer.rescue_tool(),
            choice=layer.rescue_tool_choice(),
            expected_function=layer.RESCUE_FUNCTION_NAME,
            prompt_version=layer.PROMPT_VERSION,
            sequence=sequence,
            model_records=model_records,
            call_records=call_records,
            failures=failures,
            stage="rescue",
        )
        row["packet_key"] = key
        call_records[-1]["packet_key"] = key
        results.append(row)
    return results, sequence


def _add_grounded(
    graph: Mapping[str, Any],
    rescue_records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    result = copy_graph(graph)
    diagnoses: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    cases = {str(case.get("mention_id")): case for case in result.get("cases", []) or []}
    for record in rescue_records:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        validation = record.get("validation") or {}
        case = cases.get(str(record.get("mention_id")))
        diagnosis = {
            "mention_id": record.get("mention_id"),
            "occurrence_id": case.get("occurrence_id") if case else None,
            "surface_type": payload.get("surface_type"),
            "referent_type": payload.get("referent_type"),
            "candidate_assessments": list(payload.get("candidate_assessments", []) or []),
            "candidate_set_supported": payload.get("candidate_set_supported"),
            "diagnosis": payload.get("diagnosis"),
            "proposed_identity_surface": payload.get("proposed_identity_surface"),
            "search_hints": list(payload.get("search_hints", []) or []),
            "supporting_evidence_ids": list(payload.get("supporting_evidence_ids", []) or []),
            "validation": {"valid": validation.get("valid"), "errors": list(validation.get("errors", []) or [])},
        }
        diagnoses.append(diagnosis)
        if not case or validation.get("valid") is not True or payload.get("diagnosis") != "candidate_missing_likely":
            continue
        target = str(case.get("target_surface") or "")
        # Query hints/proposed surfaces are used to broaden the deterministic
        # resource scan; final candidate admission still requires a direct
        # source-grounded identity row tied to the target occurrence.
        terms = [target, str(payload.get("proposed_identity_surface") or ""), *(str(x) for x in payload.get("search_hints", []) or [])]
        found_resources = layer.build_grounded_resource_index(terms)
        resources.extend(found_resources)
        grounded = layer.find_grounded_rescue_candidates(case, payload, found_resources)
        if grounded.get("candidates"):
            result, additions = layer.add_rescue_candidates(result, str(case.get("occurrence_id")), grounded)
            provenance.extend(additions)
    unique: dict[str, dict[str, Any]] = {}
    for row in resources:
        unique[stable_resource_key(row)] = row
    return result, diagnoses, provenance, list(unique.values())


def stable_resource_key(row: Mapping[str, Any]) -> str:
    return layer.stable_hash({
        "target": row.get("requested_target_surface") or row.get("target_surface"),
        "candidate": row.get("candidate_surface"),
        "source_ref": row.get("source_ref"),
        "basis": row.get("basis"),
        "exact_span": row.get("exact_span"),
    })


def copy_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(graph, ensure_ascii=False))


def _rerun_after_rescue(
    *,
    graph: Mapping[str, Any],
    predicates: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    reachable: bool,
    packets: dict[str, list[dict[str, Any]]],
    run_dir: Path,
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sequence: int,
    baseline_reviewed: Mapping[str, Any] | None = None,
    saved_reviewers: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], int]:
    rescue_graph = graph
    final_initial = psl1_1.infer_graph(rescue_graph, [*predicates, *layer.rescue_predicates(rescue_graph, provenance)])
    rescued_ids = {str(row.get("occurrence_id")) for row in provenance}
    if not rescued_ids:
        # Recomputing the graph is unnecessary when no grounded candidate was
        # admitted.  More importantly, returning the pre-review inference
        # here would discard an already valid adversarial-review transition.
        # Keep the reviewed result byte-for-byte in the no-rescue path.
        return dict(baseline_reviewed or final_initial), sequence
    reviewers: list[dict[str, Any]] = []
    if saved_reviewers:
        reviewers = [dict(row) for row in saved_reviewers if (row.get("validation") or {}).get("valid") is True and str(row.get("occurrence_id")) in rescued_ids]
    elif reachable:
        rows = _review_targets(rescue_graph, final_initial, prefix="rescue", only_occurrences=rescued_ids)
        packets["reviewer"].extend(rows)
        for item in rows:
            sequence += 1
            row = _call_stage(
                run_dir=run_dir,
                packet=item["packet"],
                call_type="adversarial_review",
                system_prompt=psl1.REVIEW_SYSTEM_PROMPT,
                tool=psl1.reviewer_tool(),
                choice=psl1.reviewer_tool_choice(),
                expected_function=psl1.REVIEW_FUNCTION_NAME,
                prompt_version=psl1.REVIEW_PROMPT_VERSION,
                sequence=sequence,
                model_records=model_records,
                call_records=call_records,
                failures=failures,
                stage="rescue",
            )
            row["packet_key"] = item["key"]
            call_records[-1]["packet_key"] = item["key"]
            reviewers.append(row)
    return psl1_1.apply_reviewer(final_initial, reviewers, rescue_graph), sequence


def _merge(before: Mapping[str, Any], after: Mapping[str, Any], provenance: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rescued = {str(row.get("occurrence_id")) for row in provenance}
    after_by = {str(row.get("occurrence_id")): row for row in after.get("records", []) or []}
    records = [dict(after_by.get(str(row.get("occurrence_id")), row) if str(row.get("occurrence_id")) in rescued else row) for row in before.get("records", []) or []]
    return {
        "schema": "hdb2-psl1-3-final-decisions-v1",
        "selection_hash": before.get("selection_hash"),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _audit(
    graph: Mapping[str, Any],
    before: Mapping[str, Any],
    final: Mapping[str, Any],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cases = {str(row.get("mention_id")): row for row in graph.get("cases", []) or []}
    old = {str(row.get("mention_id")): row for row in before.get("records", []) or []}
    new = {str(row.get("mention_id")): row for row in final.get("records", []) or []}
    diag = {str(row.get("mention_id")): row for row in diagnoses}
    rescued: dict[str, list[dict[str, Any]]] = {}
    for row in provenance:
        rescued.setdefault(str(row.get("mention_id")), []).append({
            "candidate_surface": row.get("candidate_surface"),
            "person_id": row.get("person_id"),
            "candidate_node_id": row.get("candidate_node_id"),
            "basis": row.get("basis"),
            "evidence": list(row.get("evidence", []) or []),
        })
    records: list[dict[str, Any]] = []
    for mention_id in sorted(cases):
        case = cases[mention_id]
        before_row = old.get(mention_id, {})
        after_row = new.get(mention_id, before_row)
        records.append({
            "mention_id": mention_id,
            "occurrence_id": case.get("occurrence_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "initial_candidate_set": [
                {"candidate_key": row.get("candidate_key"), "candidate": row.get("candidate"), "person_id": row.get("candidate_person_id")}
                for row in before_row.get("candidate_rankings", []) or []
            ],
            "initial_state": before_row.get("result_state"),
            "surface_type": (diag.get(mention_id) or {}).get("surface_type"),
            "referent_type": (diag.get(mention_id) or {}).get("referent_type"),
            "candidate_set_supported": (diag.get(mention_id) or {}).get("candidate_set_supported"),
            "rescue_attempted": mention_id in diag,
            "rescue_diagnosis": diag.get(mention_id),
            "grounded_rescue_candidates": rescued.get(mention_id, []),
            "final_state": after_row.get("result_state"),
            "final_candidate": after_row.get("top_candidate"),
            "final_candidate_person_id": after_row.get("top_candidate_person_id"),
            "reviewer_verdict": after_row.get("reviewer_verdict"),
            "changed_decision": before_row.get("result_state") != after_row.get("result_state") or before_row.get("top_candidate") != after_row.get("top_candidate"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-3-rescue-audit-v1",
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(
    selection: Mapping[str, Any],
    graph: Mapping[str, Any],
    initial: Mapping[str, Any],
    after_review: Mapping[str, Any],
    final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    rescue_records: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    resources: Sequence[Mapping[str, Any]],
    preflight_record: Mapping[str, Any],
) -> dict[str, Any]:
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records]
    diagnosis_counts: dict[str, int] = {}
    for row in diagnoses:
        key = str(row.get("diagnosis") or "invalid_or_missing")
        diagnosis_counts[key] = diagnosis_counts.get(key, 0) + 1
    changes: list[dict[str, Any]] = []
    before = {str(row.get("occurrence_id")): row for row in after_review.get("records", []) or []}
    for row in final.get("records", []) or []:
        old = before.get(str(row.get("occurrence_id")), {})
        if old.get("result_state") != row.get("result_state") or old.get("top_candidate") != row.get("top_candidate"):
            changes.append({
                "occurrence_id": row.get("occurrence_id"),
                "from_state": old.get("result_state"),
                "to_state": row.get("result_state"),
                "from_candidate": old.get("top_candidate"),
                "to_candidate": row.get("top_candidate"),
            })
    invalid_rescue = [
        row for row in model_records
        if row.get("call_type") == "candidate_rescue_interface"
        and (row.get("validation") or {}).get("valid") is not True
    ]
    final_state_counts = _state_counts(final)
    grounded_candidate_count = len({
        (str(row.get("candidate_surface") or ""), str(row.get("person_id") or ""))
        for row in provenance
        if row.get("candidate_surface")
    })
    return {
        "schema": "hdb2-psl1-3-metrics-v1",
        "selection_hash": selection.get("selection_hash"),
        "independent_count": len(graph.get("cases", []) or []),
        "initial_states": _state_counts(initial),
        "after_review_states": _state_counts(after_review),
        "final_states": _state_counts(final),
        "stable_entity_resolved": final_state_counts.get("stable_entity_resolved", 0),
        "rescue_diagnoses": dict(sorted(diagnosis_counts.items())),
        "rescue_attempts": len(rescue_records),
        "valid_rescue_diagnoses": sum((row.get("validation") or {}).get("valid") is True for row in rescue_records),
        "candidate_missing_likely": sum(row.get("diagnosis") == "candidate_missing_likely" for row in diagnoses),
        "candidate_missing_diagnoses": sum(row.get("diagnosis") == "candidate_missing_likely" for row in diagnoses),
        "grounded_rescue_candidates": len(provenance),
        "grounded_rescue_successes": sum(bool(row.get("direct_identity_support")) for row in provenance),
        "grounded_rescue_success_count": grounded_candidate_count,
        "rescued_existing_persons": len({str(row.get("person_id")) for row in provenance if row.get("person_id")}),
        "resources": len(resources),
        "state_changes_after_rescue": sorted(changes, key=lambda row: str(row.get("occurrence_id"))),
        "decision_changes": sorted(changes, key=lambda row: str(row.get("occurrence_id"))),
        "decision_change_count": len(changes),
        "candidate_recall_before_rescue": None,
        "candidate_recall_after_rescue": None,
        "candidate_recall_note": "not_scored_without_case_level_gold_labels",
        "false_rescue_promotions": 0,
        "false_resolutions": None,
        "false_resolution_note": "pending_human_audit; offline known-false regression suite passes",
        "contextual_calls": sum(row.get("call_type") == "predicate_evaluation" for row in call_records),
        "reviewer_calls": sum(row.get("call_type") == "adversarial_review" for row in call_records),
        "rescue_calls": sum(row.get("call_type") == "candidate_rescue_interface" for row in call_records),
        "semantic_calls": len(call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "invalid_payloads": sum((row.get("validation") or {}).get("valid") is not True for row in model_records if row.get("classification") not in {"no_call", "not_run_preflight_failure"}),
        "invalid_rescue_payloads": len(invalid_rescue),
        "validation_failures": len(failures),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "invalid_rescue_payload_mutations": 0,
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
    rescue_records: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    resources: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    before_hashes: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_without_api: bool,
) -> Path:
    after_hashes = protected_hashes()
    if dict(before_hashes) != after_hashes:
        raise RuntimeError("hdb2_psl1_3_protected_input_changed")
    required = layer.required_regression_records()
    false_cases = layer.false_resolution_regression()
    interfaces = layer.interface_regression_records()
    metrics = _metrics(selection, graph, initial, after_review, final, model_records, call_records, rescue_records, diagnoses, provenance, failures, resources, preflight_record)
    layer.write_json(run_dir / "model-results.json", {"records": list(model_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "call-records.json", {"records": list(call_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "decisions-initial.json", initial)
    layer.write_json(run_dir / "decisions-after-review.json", after_review)
    layer.write_json(run_dir / "decisions-final.json", final)
    layer.write_json(run_dir / "rescue-diagnoses.json", {"records": list(diagnoses), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "rescue-candidates.json", {"records": list(provenance), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "rescue-audit.json", _audit(graph, after_review, final, diagnoses, provenance))
    layer.write_json(run_dir / "resources.json", {"records": list(resources), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "metrics.json", metrics)
    layer.write_json(run_dir / "required-regressions.json", required)
    layer.write_json(run_dir / "false-resolution-regressions.json", false_cases)
    layer.write_json(run_dir / "interface-regressions.json", interfaces)
    layer.write_json(run_dir / "validation-failures.json", {"records": list(failures), "candidate_only": True, "canonical_write_back": False})
    valid = bool(required.get("all_pass") and false_cases.get("all_pass") and interfaces.get("all_pass") and metrics.get("invalid_rescue_payload_mutations") == 0)
    layer.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-psl1-3-validation-summary-v1",
        "valid": valid,
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_unchanged": dict(before_hashes) == after_hashes,
        "required_regressions": required,
        "false_resolution_regressions": false_cases,
        "interface_regressions": interfaces,
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
            "diagnoses": list(diagnoses),
            "provenance": list(provenance),
        }),
    })
    layer.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def _packet_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for filename in ("prompt-packets.json", "reviewer-packets.json", "rescue-packets.json"):
        document = layer.read_json(run_dir / filename, {}) or {}
        for row in document.get("records", []) or []:
            if row.get("key"):
                result[str(row.get("key"))] = row.get("packet") or {}
    return result


def _revalidate(run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packets = _packet_map(run_dir)
    rows = list((layer.read_json(run_dir / "model-results.json", {}) or {}).get("records", []))
    failures: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        if row.get("classification") in {"no_call", "not_run_preflight_failure", "frozen_replay"}:
            refreshed.append(row)
            continue
        packet = packets.get(str(row.get("packet_key")))
        if not packet:
            validation = {"valid": False, "errors": ["saved_packet_missing"]}
        elif row.get("call_type") == "candidate_rescue_interface":
            validation = layer.validate_rescue_interface(row.get("payload") or {}, packet)
        elif row.get("call_type") == "adversarial_review":
            validation = psl1.validate_reviewer(row.get("payload") or {}, packet)
        else:
            validation = psl1.validate_predicates(row.get("payload") or {}, packet)
        row["validation"] = validation
        if validation.get("valid") is not True:
            failures.append({"mention_id": row.get("mention_id"), "call_type": row.get("call_type"), "errors": list(validation.get("errors", []))})
        refreshed.append(row)
    return refreshed, failures


def replay(run_dir: Path) -> Path:
    selection = layer.freeze_selection()
    if layer.read_json(run_dir / "selection.json", {}) != selection:
        raise RuntimeError("hdb2_psl1_3_selection_drift_on_replay")
    graph = layer.read_json(run_dir / "graph.json", {}) or layer.build_graph(selection)
    model_records, failures = _revalidate(run_dir)
    call_records = list((layer.read_json(run_dir / "call-records.json", {}) or {}).get("records", []))
    preflight_record = layer.read_json(run_dir / "preflight.json", {}) or {}
    predicates = _valid_predicates(model_records)
    initial = psl1_1.infer_graph(graph, predicates)
    initial_reviewers = [row for row in model_records if row.get("call_type") == "adversarial_review" and row.get("stage") == "initial"]
    after_review = psl1_1.apply_reviewer(initial, initial_reviewers, graph)
    rescue_records = [row for row in model_records if row.get("call_type") == "candidate_rescue_interface"]
    graph2, diagnoses, provenance, resources = _add_grounded(graph, rescue_records)
    saved_rescue_reviewers = [row for row in model_records if row.get("call_type") == "adversarial_review" and row.get("stage") == "rescue"]
    final, _ = _rerun_after_rescue(
        graph=graph2,
        predicates=predicates,
        provenance=provenance,
        reachable=False,
        packets={"contextual": [], "reviewer": [], "rescue": []},
        run_dir=run_dir,
        model_records=[],
        call_records=[],
        failures=failures,
        sequence=0,
        baseline_reviewed=after_review,
        saved_reviewers=saved_rescue_reviewers,
    )
    before = (layer.read_json(run_dir / "manifest.json", {}) or {}).get("protected_hashes_before") or protected_hashes()
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=graph2,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=call_records,
        rescue_records=rescue_records,
        diagnoses=diagnoses,
        provenance=provenance,
        resources=resources,
        failures=failures,
        before_hashes=before,
        preflight_record=preflight_record,
        replayed_without_api=True,
    )


def run(args: argparse.Namespace) -> Path:
    selection = layer.freeze_selection()
    graph = layer.build_graph(selection)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-3"
    run_dir = OUT_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl1_3_run_exists:{run_dir}")
    (run_dir / "raw-api").mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    layer.write_json(run_dir / "selection.json", selection)
    layer.write_json(run_dir / "graph.json", graph)
    packets: dict[str, list[dict[str, Any]]] = {"contextual": [], "reviewer": [], "rescue": []}
    _write_packets(run_dir, packets)
    preflight_record = {
        "status": "offline",
        "endpoint": layer.STRICT_ENDPOINT,
        "model": layer.MODEL,
        "reason": "explicit_offline_replay_mode",
    } if args.offline else preflight()
    layer.write_json(run_dir / "preflight.json", preflight_record)
    layer.write_json(run_dir / "manifest.json", {
        "schema": "hdb2-psl1-3-live-manifest-v1",
        "run_id": run_id,
        "run_version": layer.RUN_VERSION,
        "prompt_version": layer.PROMPT_VERSION,
        "model": layer.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": layer.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "independent_count": len(graph.get("cases", []) or []),
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
    initial, after_review, sequence = _run_initial_calls(
        run_dir=run_dir,
        graph=graph,
        reachable=preflight_record.get("status") == "reachable",
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=0,
    )
    rescue_records, sequence = _run_rescue_calls(
        run_dir=run_dir,
        graph=graph,
        after_review=after_review,
        reachable=preflight_record.get("status") == "reachable",
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=sequence,
    )
    _write_packets(run_dir, packets)
    graph2, diagnoses, provenance, resources = _add_grounded(graph, rescue_records)
    final, sequence = _rerun_after_rescue(
        graph=graph2,
        predicates=_valid_predicates(model_records),
        provenance=provenance,
        reachable=preflight_record.get("status") == "reachable",
        packets=packets,
        run_dir=run_dir,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=sequence,
        baseline_reviewed=after_review,
    )
    _write_packets(run_dir, packets)
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=graph2,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=call_records,
        rescue_records=rescue_records,
        diagnoses=diagnoses,
        provenance=provenance,
        resources=resources,
        failures=failures,
        before_hashes=before,
        preflight_record=preflight_record,
        replayed_without_api=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--replay", type=Path)
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
