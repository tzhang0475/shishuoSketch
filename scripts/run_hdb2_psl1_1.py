#!/usr/bin/env python3
"""Run HDB2-PSL1.1 without changing the frozen PSL1 experiment.

The 44 PSL1 cases are replayed from their immutable model outputs.  Only the
new, deterministic reference-structure layer is applied to that replay.  A
separate frozen ten-occurrence selection receives the bounded live predicate
and adversarial-review calls.  Every output remains candidate-only.
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

import hdb2_lj0_common as lj0  # noqa: E402
import hdb2_psl1_1_common as layer  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
from run_hdb2_psl1 import (  # noqa: E402
    _call_tool,
    _raw_path,
    finish_reason,
    preflight,
    protected_hashes,
    safe_error,
    usage,
    utc_now,
)


OUT_ROOT = ROOT / "data/generated/hdb2-psl1-1/live"
SELECTION_PATH = layer.SELECTION_PATH
OLD_REGRESSION = layer.PSL1_RUN / "decisions-final-regression.json"
OLD_HOLDOUT = layer.PSL1_RUN / "decisions-final-holdout.json"


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    layer.write_json(path, value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): _sha256(path)
        for path in sorted(raw_dir.glob("*.json"))
    }


def _graph_for_independent(selection: Mapping[str, Any]) -> dict[str, Any]:
    # This is the same LJ0 SELECT/candidate builder used by PSL1.  The frozen
    # selection identifies the rows; the committed review projection supplies
    # the original evidence fields.  No result is used to construct the live
    # packet, and the selection file itself remains a compact frozen index.
    review_items = {
        str(row.get("occurrence_id")): row
        for row in lj0.load_review_items()
        if row.get("occurrence_id")
    }
    cases = []
    for selected in selection.get("independent_cases", []):
        occurrence_id = str(selected.get("occurrence_id"))
        source = review_items.get(occurrence_id)
        if source is None:
            raise RuntimeError(f"psl1_1_selection_item_missing:{occurrence_id}")
        cases.append(dict(source))
    cases_document = lj0.build_cases({
        "schema": "hdb2-psl1-1-independent-input-v1",
        "selection_hash": selection.get("selection_hash"),
        "cases": cases,
    })
    return layer.augment_graph(psl1.build_graph_cases(cases_document))


def _group_for_mention(mention_id: str, graphs: Sequence[Mapping[str, Any]]) -> str:
    for group, graph in graphs:
        if any(str(case.get("mention_id")) == mention_id for case in graph.get("cases", [])):
            return group
    return "unknown"


def _frozen_development_records(graphs: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reuse PSL1 responses as replay data, without pretending to revalidate
    their old packets against the augmented graph.

    The old predicate response is still a valid historical experiment output;
    newly added candidates receive no invented predicate values.  This is the
    required offline path for the three development regressions.
    """
    records: list[dict[str, Any]] = []
    reviewers: list[dict[str, Any]] = []
    for source in (layer.load_frozen_predicate_records(), layer.load_frozen_reviewer_records()):
        for original in source:
            row = dict(original)
            mention_id = str(row.get("mention_id") or "")
            row["group"] = _group_for_mention(mention_id, graphs)
            row["classification"] = "frozen_replay"
            if row.get("call_type") == "predicate_evaluation":
                # Existing invalid payloads remain invalid and are never fed
                # to inference.  Valid old payloads are marked as replayed;
                # no new candidate can be assigned a guessed value.
                if not isinstance(row.get("payload"), Mapping):
                    row["validation"] = {"valid": False, "errors": ["frozen_payload_missing"]}
                else:
                    row["validation"] = {"valid": True, "errors": [], "frozen_replay": True}
                records.append(row)
            elif row.get("call_type") == "adversarial_review":
                reviewers.append(row)
    return records, reviewers


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


def _call_record_failure(record: Mapping[str, Any], failure: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not failure:
        return None
    return {
        "sequence": record.get("sequence"),
        "call_type": record.get("call_type"),
        "mention_id": record.get("mention_id"),
        "classification": record.get("classification"),
        "errors": list(failure.get("errors", [])),
    }


def _state_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        state = str(row.get("result_state") or "")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def _unique_model_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep one immutable model record per call in downstream artifacts."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for original in records:
        row = dict(original)
        key = (
            row.get("group"),
            row.get("call_type"),
            row.get("mention_id"),
            row.get("sequence"),
            row.get("request_hash"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _decision_by_occurrence(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("occurrence_id")): dict(row) for row in document.get("records", [])}


def _load_old_psl1() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in (OLD_REGRESSION, OLD_HOLDOUT):
        for occurrence_id, row in _decision_by_occurrence(read_json(path, {}) or {}).items():
            result[occurrence_id] = row
    return result


def _development_comparison(final: Mapping[str, Any]) -> dict[str, Any]:
    old = _load_old_psl1()
    rows: list[dict[str, Any]] = []
    for row in final.get("records", []):
        occurrence_id = str(row.get("occurrence_id"))
        previous = old.get(occurrence_id, {})
        changed = (
            row.get("result_state") != previous.get("result_state")
            or row.get("top_candidate") != previous.get("top_candidate")
        )
        rows.append({
            "occurrence_id": occurrence_id,
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "psl1_state": previous.get("result_state"),
            "psl1_candidate": previous.get("top_candidate"),
            "psl1_1_state": row.get("result_state"),
            "psl1_1_candidate": row.get("top_candidate"),
            "changed": changed,
            "change_reason": (
                "reference_structure_veto"
                if row.get("reference_structure_veto_count")
                else "state_or_candidate_changed"
                if changed
                else "unchanged"
            ),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    rows.sort(key=lambda row: str(row.get("occurrence_id")))
    return {
        "schema": "hdb2-psl1-1-development-comparison-v1",
        "records": rows,
        "changed_count": sum(bool(row.get("changed")) for row in rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _required_development_outcomes(graphs: Sequence[Mapping[str, Any]], final: Mapping[str, Any]) -> dict[str, Any]:
    by_key = {(str(row.get("story_id")), str(row.get("surface"))): row for row in final.get("records", [])}
    checks = {
        "主→王敦_disappears": ("34-pilou-001", "主", "王敦"),
        "謝豫章→謝尚_disappears": ("02-yanyu-046", "謝豫章", "謝尚"),
        "敦主簿→王敦_disappears": ("05-fangzheng-028", "敦主簿", "王敦"),
    }
    result: dict[str, Any] = {}
    for name, (story_id, surface, wrong) in checks.items():
        row = by_key.get((story_id, surface), {})
        result[name] = {
            "pass": not (
                row.get("top_candidate") == wrong
                and row.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"}
            ),
            "story_id": story_id,
            "surface": surface,
            "wrong_candidate": wrong,
            "final_state": row.get("result_state"),
            "final_candidate": row.get("top_candidate"),
            "role_vetoes": row.get("role_vetoes", {}),
        }
    expected = {
        ("虎賁中郎將", "潘岳"),
        ("侍中", "謝安"),
        ("僕射", "周顗"),
        ("豫章太守", "謝鯤"),
        ("丞相", "王導"),
        ("劉尹", "劉惔"),
        ("丹陽尹", "劉惔"),
        ("太傅", "謝安"),
    }
    stable_checks: list[dict[str, Any]] = []
    for row in final.get("records", []):
        key = (str(row.get("surface")), str(row.get("top_candidate")))
        if key not in expected:
            continue
        stable_checks.append({
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "expected_candidate": row.get("top_candidate"),
            "state": row.get("result_state"),
            "available": row.get("result_state") == "stable_entity_resolved",
        })
    result["known_supported_cases"] = stable_checks
    expected_pass = {
        ("02-yanyu-107", "虎賁中郎將", "潘岳"),
        ("25-paidiao-038", "侍中", "謝安"),
        ("05-fangzheng-030", "僕射", "周顗"),
        ("10-guizhen-012", "豫章太守", "謝鯤"),
        ("02-yanyu-036", "丞相", "王導"),
        ("02-yanyu-054", "劉尹", "劉惔"),
        ("02-yanyu-069", "丹陽尹", "劉惔"),
        ("08-shangyu-051", "長史", "謝鯤"),
        ("19-xianyuan-026", "太傅", "謝安"),
    }
    found_expected = {
        (str(row.get("story_id")), str(row.get("surface")), str(row.get("top_candidate")))
        for row in final.get("records", [])
        if row.get("result_state") == "stable_entity_resolved"
    }
    result["known_supported_pass"] = expected_pass.issubset(found_expected)
    result["all_required_pass"] = (
        all(bool(value.get("pass")) for key, value in result.items() if key not in {"known_supported_cases", "known_supported_pass"})
        and result["known_supported_pass"]
    )
    return result


def _audit_independent(graph: Mapping[str, Any], decisions: Mapping[str, Any], reviewer_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    case_by_id = {str(row.get("mention_id")): row for row in graph.get("cases", [])}
    review_by_id = {str(row.get("mention_id")): row for row in reviewer_rows}
    result: list[dict[str, Any]] = []
    for decision in sorted(decisions.get("records", []), key=lambda row: str(row.get("occurrence_id"))):
        case = case_by_id.get(str(decision.get("mention_id")), {})
        top = next((row for row in decision.get("candidate_rankings", []) if row.get("candidate_key") == decision.get("top_candidate_key")), {})
        review = review_by_id.get(str(decision.get("mention_id")), {})
        payload = review.get("payload") or {}
        result.append({
            "story_id": decision.get("story_id"),
            "surface": decision.get("surface"),
            "candidate": decision.get("top_candidate"),
            "person_id": decision.get("top_candidate_person_id"),
            "final_state": decision.get("result_state"),
            "psl_link": top.get("link"),
            "reviewer_verdict": payload.get("verdict"),
            "direct_identity_evidence": list(payload.get("direct_identity_support", [])),
            "negative_evidence": list(payload.get("identity_contradictions", [])),
            "reference_structure": decision.get("reference_structure", {}),
            "collective_predicates": decision.get("collective_support_predicates", []),
            "candidate_rankings": decision.get("candidate_rankings", []),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return result


def _metrics(
    *,
    development_initial: Mapping[str, Any],
    development_final: Mapping[str, Any],
    independent_initial: Mapping[str, Any],
    independent_final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    development_graphs: Sequence[Mapping[str, Any]],
    independent_graph: Mapping[str, Any],
    development_reviewers: Sequence[Mapping[str, Any]],
    independent_reviewers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    dev_initial = list(development_initial.get("records", []))
    dev_final = list(development_final.get("records", []))
    ind_initial = list(independent_initial.get("records", []))
    ind_final = list(independent_final.get("records", []))
    all_final = [*dev_final, *ind_final]
    all_initial = [*dev_initial, *ind_initial]
    states = _state_counts(all_final)
    initial_states = _state_counts(all_initial)
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records]
    valid_reviews = [*development_reviewers, *independent_reviewers]
    valid_reviews = [row for row in valid_reviews if (row.get("validation") or {}).get("valid") is True]
    role_vetoes = sum(int(row.get("reference_structure_veto_count") or 0) for row in all_initial)
    independent_categories: dict[str, int] = {}
    for case in independent_graph.get("cases", []):
        for category in (case.get("selection_categories") or []):
            independent_categories[str(category)] = independent_categories.get(str(category), 0) + 1
    # No truth-labelled gold set is introduced by this patch.  The safety and
    # development-case checks are reported instead of inventing recall.
    return {
        "schema": "hdb2-psl1-1-metrics-v1",
        "development_count": len(dev_final),
        "independent_count": len(ind_final),
        "development_initial_states": _state_counts(dev_initial),
        "development_final_states": _state_counts(dev_final),
        "independent_initial_states": _state_counts(ind_initial),
        "independent_final_states": _state_counts(ind_final),
        "initial_result_states": initial_states,
        "result_states": states,
        "explicit_resolved": states.get("stable_entity_resolved", 0),
        "contextually_resolved": states.get("stable_entity_resolved", 0),
        "contextually_preferred": states.get("review_required", 0),
        "compositional_reference": states.get("structural_reference", 0),
        "unresolved": states.get("genuinely_unresolved", 0),
        "review_required": states.get("review_required", 0),
        "role_veto_count": role_vetoes,
        "hard_veto_count": sum(int(row.get("hard_veto_count") or 0) for row in all_initial),
        "reviewer_calls": sum(str(row.get("call_type")) == "adversarial_review" for row in call_records),
        "valid_reviewer_payloads": len(valid_reviews),
        "reviewer_resolved": sum(bool(row.get("reviewer_resolved")) for row in all_final),
        "reviewer_rejected_top_candidate": sum(bool(row.get("reviewer_rejected_top_candidate")) for row in all_final),
        # Malformed provider payloads are diagnostics, not state mutations.
        # Keep them separate from the hard safety counters, which remain zero
        # when the invalid payload is fail-closed.
        "invalid_candidate_key_payloads": sum("candidate" in str(error).lower() and "invalid" in str(error).lower() for row in failures for error in row.get("errors", [])),
        "invalid_evidence_reference_payloads": sum("evidence_reference_invalid" in str(error) for row in failures for error in row.get("errors", [])),
        "invalid_candidate_keys": 0,
        "invalid_evidence_references": 0,
        "validation_failures": len(failures),
        "independent_selection_categories": dict(sorted(independent_categories.items())),
        "predicate_calls": sum(str(row.get("call_type")) == "predicate_evaluation" for row in call_records),
        "semantic_calls": len(call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _finalize(
    *,
    run_dir: Path,
    selection: Mapping[str, Any],
    development_graphs: Sequence[Mapping[str, Any]],
    independent_graph: Mapping[str, Any],
    development_records: Sequence[Mapping[str, Any]],
    independent_records: Sequence[Mapping[str, Any]],
    development_reviewers: Sequence[Mapping[str, Any]],
    independent_reviewers: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    before: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_development_without_api: bool,
) -> Path:
    dev_predicates = _valid_predicates(development_records)
    ind_predicates = _valid_predicates(independent_records)
    dev_initial = [layer.infer_graph(graph, dev_predicates) for graph in development_graphs]
    dev_final = [
        layer.apply_reviewer(initial, development_reviewers, graph)
        for initial, graph in zip(dev_initial, development_graphs)
    ]
    independent_initial = layer.infer_graph(independent_graph, ind_predicates)
    independent_final = layer.apply_reviewer(independent_initial, independent_reviewers, independent_graph)
    all_initial = {
        "records": [row for document in dev_initial for row in document.get("records", [])] + list(independent_initial.get("records", [])),
    }
    all_final = {
        "records": [row for document in dev_final for row in document.get("records", [])] + list(independent_final.get("records", [])),
    }
    validation_rows = list(failures)
    safety = layer.safety_metrics([*development_graphs, independent_graph], all_final["records"], validation_rows)
    metrics = _metrics(
        development_initial={"records": [row for document in dev_initial for row in document.get("records", [])]},
        development_final={"records": [row for document in dev_final for row in document.get("records", [])]},
        independent_initial=independent_initial,
        independent_final=independent_final,
        model_records=[*development_records, *independent_records],
        call_records=call_records,
        failures=validation_rows,
        development_graphs=development_graphs,
        independent_graph=independent_graph,
        development_reviewers=development_reviewers,
        independent_reviewers=independent_reviewers,
    )
    metrics["development_replayed_without_api"] = replayed_development_without_api
    metrics["preflight"] = dict(preflight_record)
    metrics["safety_metrics"] = safety
    metrics["false_resolution_candidates"] = sum(
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
    metrics["independent_selection_categories"] = dict(sorted({
        category: sum(category in (row.get("selection_categories") or []) for row in selection.get("independent_cases", []))
        for category in sorted({
            category
            for row in selection.get("independent_cases", [])
            for category in row.get("selection_categories", []) or []
        })
    }.items()))
    metrics["live_independent_validation_complete"] = (
        preflight_record.get("status") == "reachable"
        and metrics.get("predicate_calls", 0) > 0
        and metrics.get("provider_failures", 0) == 0
        and metrics.get("parse_failures", 0) == 0
        and metrics.get("truncated_responses", 0) == 0
    )
    required = _required_development_outcomes(development_graphs, {"records": [row for document in dev_final for row in document.get("records", [])]})
    metrics["required_development_outcomes"] = required
    comparison = _development_comparison({"records": [row for document in dev_final for row in document.get("records", [])]})
    independent_audit = _audit_independent(independent_graph, independent_final, independent_reviewers)
    after = protected_hashes()
    if dict(before) != after:
        raise RuntimeError("hdb2_psl1_1_protected_input_changed")
    all_model_records = _unique_model_records([
        *development_records,
        *development_reviewers,
        *independent_records,
        *independent_reviewers,
    ])
    write_json(run_dir / "model-results.json", {"records": all_model_records, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "decisions-initial-development.json", {"groups": dev_initial, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "decisions-final-development.json", {"groups": dev_final, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "decisions-initial-independent.json", independent_initial)
    write_json(run_dir / "decisions-final-independent.json", independent_final)
    write_json(run_dir / "development-comparison.json", comparison)
    write_json(run_dir / "independent-audit.json", {"records": independent_audit, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "safety.json", safety)
    write_json(run_dir / "validation-failures.json", {"records": validation_rows, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "required-development-outcomes.json", required)
    summary = {
        "schema": "hdb2-psl1-1-validation-summary-v1",
        "valid": (
            not metrics.get("false_resolution_candidates")
            and required.get("all_required_pass")
            and metrics.get("live_independent_validation_complete") is True
        ),
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_unchanged": dict(before) == after,
        "development_replayed_without_api": replayed_development_without_api,
        "validation_failures": len(validation_rows),
        "payload_validation_clean": not validation_rows,
        "payload_validation_note": "Rejected provider payloads are retained as diagnostics and never mutate identity state.",
        "safety_metrics": safety,
        "required_development_outcomes": required,
    }
    write_json(run_dir / "validation-summary.json", summary)
    manifest = read_json(run_dir / "manifest.json", {}) or {}
    manifest.update({
        "status": "complete",
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "replayed_development_without_api": replayed_development_without_api,
        "semantic_calls": len(call_records),
        "protected_hashes_before": dict(before),
        "protected_hashes_after": after,
        "raw_api_hashes": _raw_hashes(run_dir / "raw-api"),
        "postprocessing_hash": layer.stable_hash({
            "graphs": [*development_graphs, independent_graph],
            "model_records": all_model_records,
            "final_development": dev_final,
            "final_independent": independent_final,
        }),
    })
    write_json(run_dir / "manifest.json", manifest)
    return run_dir


def _prepare_packets(
    *,
    development_graphs: Sequence[Mapping[str, Any]],
    independent_graph: Mapping[str, Any],
    run_dir: Path,
) -> tuple[list[dict[str, Any]], list[tuple[Mapping[str, Any], Mapping[str, Any], dict[str, Any]]]]:
    packets: list[dict[str, Any]] = []
    independent_cases: list[tuple[Mapping[str, Any], Mapping[str, Any], dict[str, Any]]] = []
    for case in independent_graph.get("cases", []):
        packet = layer.wire_packet(case, independent_graph.get("cases", []), independent_graph)
        packets.append({"key": f"predicate:{case.get('mention_id')}", "packet": packet})
        independent_cases.append((case, independent_graph, packet))
    write_json(run_dir / "prompt-packets.json", {"records": packets, "candidate_only": True, "canonical_write_back": False})
    # Development packets are audit-only.  They are deliberately not sent to
    # the provider in this run.
    development_packets = []
    for index, graph in enumerate(development_graphs):
        for case in graph.get("cases", []):
            development_packets.append({
                "key": f"development-{index}:predicate:{case.get('mention_id')}",
                "packet": layer.wire_packet(case, graph.get("cases", []), graph),
                "sent_to_provider": False,
            })
    write_json(run_dir / "development-prompt-packets.json", {"records": development_packets, "candidate_only": True, "canonical_write_back": False})
    return packets, independent_cases


def run(args: argparse.Namespace) -> Path:
    selection = layer.freeze_selection(SELECTION_PATH)
    development_graphs = list(layer.load_psl1_graphs())
    independent_graph = _graph_for_independent(selection)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-1"
    run_dir = OUT_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl1_1_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    write_json(run_dir / "selection.json", selection)
    write_json(run_dir / "graph-development-regression.json", development_graphs[0])
    write_json(run_dir / "graph-development-holdout.json", development_graphs[1])
    write_json(run_dir / "graph-independent.json", independent_graph)
    _prepare_packets(development_graphs=development_graphs, independent_graph=independent_graph, run_dir=run_dir)
    preflight_record = preflight()
    write_json(run_dir / "preflight.json", preflight_record)
    manifest = {
        "schema": "hdb2-psl1-1-live-manifest-v1",
        "run_id": run_id,
        "run_version": layer.RUN_VERSION,
        "prompt_version": layer.PROMPT_VERSION,
        "review_prompt_version": layer.REVIEW_PROMPT_VERSION,
        "model": layer.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": layer.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "development_regression_count": len(development_graphs[0].get("cases", [])),
        "development_holdout_count": len(development_graphs[1].get("cases", [])),
        "independent_count": len(independent_graph.get("cases", [])),
        "development_replayed_without_api": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": before,
        "preflight": preflight_record,
        "created_at": utc_now(),
    }
    write_json(run_dir / "manifest.json", manifest)
    frozen_development, frozen_development_reviewers = _frozen_development_records((
        ("development_regression", development_graphs[0]),
        ("development_holdout", development_graphs[1]),
    ))
    model_records: list[dict[str, Any]] = list(frozen_development)
    independent_predicate_records: list[dict[str, Any]] = []
    independent_reviewer_records: list[dict[str, Any]] = []
    independent_call_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if preflight_record.get("status") == "reachable":
        sequence = 0
        for case in independent_graph.get("cases", []):
            packet = layer.wire_packet(case, independent_graph.get("cases", []), independent_graph)
            if not packet.get("request_predicates"):
                independent_predicate_records.append({
                    "sequence": None,
                    "call_type": "predicate_evaluation",
                    "mention_id": case.get("mention_id"),
                    "story_id": case.get("story_id"),
                    "payload": {"predicates": [], "note": "no_requested_llm_predicates"},
                    "validation": {"valid": True, "errors": []},
                    "classification": "no_call",
                    "group": "independent",
                })
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
                prompt_version=layer.PROMPT_VERSION,
                raw_dir=raw_dir,
                validator=psl1.validate_predicates,
            )
            call_record["group"] = "independent"
            model_record["group"] = "independent"
            independent_call_records.append(call_record)
            independent_predicate_records.append(model_record)
            failure_row = _call_record_failure(call_record, failure)
            if failure_row:
                failures.append(failure_row)
        initial_independent = layer.infer_graph(independent_graph, _valid_predicates(independent_predicate_records))
        reviewer_packets: list[dict[str, Any]] = []
        reviewer_targets: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
        initial_by_id = {str(row.get("mention_id")): row for row in initial_independent.get("records", [])}
        for case in independent_graph.get("cases", []):
            decision = initial_by_id.get(str(case.get("mention_id")))
            if not decision or decision.get("result_state") not in {"stable_entity_resolved", "review_required"}:
                continue
            packet = layer.reviewer_packet(case, independent_graph.get("cases", []), independent_graph, decision)
            reviewer_packets.append({"key": f"review:{case.get('mention_id')}", "packet": packet})
            reviewer_targets.append((case, packet))
        write_json(run_dir / "reviewer-packets.json", {"records": reviewer_packets, "candidate_only": True, "canonical_write_back": False})
        for case, packet in reviewer_targets:
            sequence += 1
            call_record, model_record, failure = _call_tool(
                packet=packet,
                sequence=sequence,
                call_type="adversarial_review",
                system_prompt=psl1.REVIEW_SYSTEM_PROMPT,
                tool=psl1.reviewer_tool(),
                choice=psl1.reviewer_tool_choice(),
                expected_function=psl1.REVIEW_FUNCTION_NAME,
                prompt_version=layer.REVIEW_PROMPT_VERSION,
                raw_dir=raw_dir,
                validator=psl1.validate_reviewer,
            )
            call_record["group"] = "independent"
            model_record["group"] = "independent"
            independent_call_records.append(call_record)
            independent_reviewer_records.append(model_record)
            failure_row = _call_record_failure(call_record, failure)
            if failure_row:
                failures.append(failure_row)
    else:
        write_json(run_dir / "reviewer-packets.json", {"records": [], "candidate_only": True, "canonical_write_back": False})
    call_records = independent_call_records
    write_json(run_dir / "call-records.json", {"records": call_records, "candidate_only": True, "canonical_write_back": False})
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        development_graphs=development_graphs,
        independent_graph=independent_graph,
        development_records=frozen_development,
        independent_records=independent_predicate_records,
        development_reviewers=frozen_development_reviewers,
        independent_reviewers=independent_reviewer_records,
        call_records=call_records,
        failures=failures,
        before=before,
        preflight_record=preflight_record,
        replayed_development_without_api=True,
    )


def replay(run_dir: Path) -> Path:
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    selection = read_json(run_dir / "selection.json", {}) or {}
    # Rebuild deterministic graph/context artifacts from the frozen selection
    # and current source builders.  The saved graph files remain immutable
    # live-run audit artifacts; replay must exercise the current boundary-safe
    # structure layer rather than silently retaining an older derived graph.
    development_graphs = list(layer.load_psl1_graphs())
    independent_graph = _graph_for_independent(selection)
    model_document = read_json(run_dir / "model-results.json", {}) or {}
    model_records = _unique_model_records(model_document.get("records", []))
    # Revalidate only records produced for the independent packets.  Frozen
    # development outputs remain an explicit offline replay.
    packets: dict[str, dict[str, Any]] = {}
    for filename in ("prompt-packets.json", "reviewer-packets.json"):
        document = read_json(run_dir / filename, {}) or {}
        packets.update({str(row.get("key")): row.get("packet") or {} for row in document.get("records", [])})
    failures: list[dict[str, Any]] = []
    for row in model_records:
        if row.get("classification") == "frozen_replay":
            continue
        mention_id = row.get("mention_id")
        key = f"review:{mention_id}" if row.get("call_type") == "adversarial_review" else f"predicate:{mention_id}"
        packet = packets.get(key, {})
        if row.get("call_type") == "adversarial_review":
            validation = psl1.validate_reviewer(row.get("payload") or {}, packet)
        else:
            validation = psl1.validate_predicates(row.get("payload") or {}, packet)
        row["validation"] = validation
        if validation.get("valid") is not True:
            failures.append({"mention_id": mention_id, "call_type": row.get("call_type"), "errors": list(validation.get("errors", []))})
    call_records = list((read_json(run_dir / "call-records.json", {}) or {}).get("records", []))
    before = (read_json(run_dir / "manifest.json", {}) or {}).get("protected_hashes_before") or protected_hashes()
    preflight_record = read_json(run_dir / "preflight.json", {}) or {}
    frozen_dev = [row for row in model_records if row.get("group") in {"development_regression", "development_holdout"} and row.get("call_type") == "predicate_evaluation"]
    frozen_reviewers = [row for row in model_records if row.get("group") in {"development_regression", "development_holdout"} and row.get("call_type") == "adversarial_review"]
    independent_predicates = [row for row in model_records if row.get("group") == "independent" and row.get("call_type") == "predicate_evaluation"]
    independent_reviewers = [row for row in model_records if row.get("group") == "independent" and row.get("call_type") == "adversarial_review"]
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        development_graphs=development_graphs,
        independent_graph=independent_graph,
        development_records=frozen_dev,
        independent_records=independent_predicates,
        development_reviewers=frozen_reviewers,
        independent_reviewers=independent_reviewers,
        call_records=call_records,
        failures=failures,
        before=before,
        preflight_record=preflight_record,
        replayed_development_without_api=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        replay(args.replay)
        return 0
    selection = layer.freeze_selection(SELECTION_PATH)
    if args.prepare_only:
        print(json.dumps({
            "selection": str(SELECTION_PATH.relative_to(ROOT)),
            "selection_hash": selection.get("selection_hash"),
            "independent_count": selection.get("independent_count"),
            "frozen_before_live": selection.get("frozen_before_live"),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
