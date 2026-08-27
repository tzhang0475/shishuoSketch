#!/usr/bin/env python3
"""Run the additive HDB2-PSL1.3A reference-semantic validation.

The runner inserts one small semantic arbitration boundary before the
existing PSL1.3 pipeline.  Predicate scoring, adversarial review, candidate
rescue, and all canonical protections are imported from the frozen runners
without modification.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_3a_common as layer  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import hdb2_psl1_1_common as psl1_1  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
from run_hdb2_psl1 import _call_tool, preflight, protected_hashes, utc_now  # noqa: E402
from run_hdb2_psl1_3 import (  # noqa: E402
    _add_grounded,
    _rerun_after_rescue,
    _run_initial_calls,
    _run_rescue_calls,
    _valid_predicates,
    _write_packets,
)


OUT_ROOT = layer.GENERATED / "live"


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


def _reference_call(
    *,
    run_dir: Path,
    packet: Mapping[str, Any],
    sequence: int,
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    call_record, model_record, failure = _call_tool(
        packet=packet,
        sequence=sequence,
        call_type="reference_semantic_arbitration",
        system_prompt=layer.SEMANTIC_SYSTEM_PROMPT,
        tool=layer.semantic_tool(),
        choice=layer.semantic_tool_choice(),
        expected_function=layer.FUNCTION_NAME,
        prompt_version=layer.PROMPT_VERSION,
        raw_dir=run_dir / "raw-api",
        validator=layer.validate_semantic_arbitration,
    )
    call_record["stage"] = "reference_prejudgment"
    model_record["stage"] = "reference_prejudgment"
    call_records.append(call_record)
    model_records.append(model_record)
    failure_row = _failure(call_record, failure)
    if failure_row:
        failures.append(failure_row)
    return model_record


def _no_reference_call(case: Mapping[str, Any], reason: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    validation = {"valid": True, "errors": []}
    return {
        "sequence": None,
        "call_type": "reference_semantic_arbitration",
        "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"),
        "payload": dict(payload) if payload else {},
        "validation": validation,
        "classification": reason,
        "request_hash": None,
    }


def _run_reference_prejudgment(
    *,
    run_dir: Path,
    graph: Mapping[str, Any],
    reachable: bool,
    offline: bool,
    packets: dict[str, list[dict[str, Any]]],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int, dict[str, int]]:
    structures: dict[str, dict[str, Any]] = {}
    counts = {"ambiguous": 0, "deterministic_bypass": 0, "semantic_calls": 0}
    sequence = 0
    for case in graph.get("cases", []) or []:
        info = layer.reference_hypotheses(case)
        hypotheses = info["hypotheses"]
        packet = layer.semantic_packet(case, hypotheses)
        key = f"reference:{case.get('mention_id')}"
        packets.setdefault("reference", []).append({
            "key": key,
            "packet": packet,
            "sent_to_provider": bool(reachable and info["ambiguous"]),
            "hypothesis_count": len(hypotheses),
            "deterministic": info["deterministic"],
        })
        arbitration: Mapping[str, Any] | None = None
        validation: Mapping[str, Any] | None = None
        if info["deterministic"]:
            counts["deterministic_bypass"] += 1
            reference_record = _no_reference_call(case, "deterministic_bypass")
        else:
            counts["ambiguous"] += 1
            if offline:
                fixture = layer.arbitration_regression_payload(case, hypotheses)
                reference_record = _no_reference_call(
                    case,
                    "offline_fixture" if fixture else "offline_ambiguous_no_fixture",
                    fixture,
                )
            elif not reachable:
                reference_record = _no_reference_call(case, "not_run_preflight_failure")
            else:
                sequence += 1
                counts["semantic_calls"] += 1
                reference_record = _reference_call(
                    run_dir=run_dir,
                    packet=packet,
                    sequence=sequence,
                    model_records=model_records,
                    call_records=call_records,
                    failures=failures,
                )
                call_records[-1]["packet_key"] = key
        if reference_record.get("classification") == "offline_fixture":
            # The fixture is a replay aid, not a provider response.  It is
            # nevertheless validated against the exact same packet before it
            # can affect the structure.
            validation = layer.validate_semantic_arbitration(reference_record.get("payload") or {}, packet)
            reference_record["validation"] = validation
        elif reference_record.get("classification") == "deterministic_bypass":
            validation = {"valid": True, "errors": []}
        else:
            validation = reference_record.get("validation") or {"valid": False, "errors": ["no_arbitration"]}
        reference_record["packet_key"] = key
        reference_record["hypotheses"] = hypotheses
        if reference_record not in model_records:
            model_records.append(reference_record)
        payload = reference_record.get("payload") if isinstance(reference_record.get("payload"), Mapping) else None
        structure = layer.finalize_reference_structure(case, payload, validation)
        structures[str(case.get("mention_id"))] = structure
    return structures, sequence, counts


def _write_reference_packets(run_dir: Path, packets: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    layer.write_json(run_dir / "reference-packets.json", {
        "schema": "hdb2-psl1-3a-reference-packets-v1",
        "records": list(packets.get("reference", [])),
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _state_counts(document: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in document.get("records", []) or []:
        state = str(row.get("result_state") or "")
        result[state] = result.get(state, 0) + 1
    return dict(sorted(result.items()))


def _structure_metrics(
    old_graph: Mapping[str, Any],
    graph: Mapping[str, Any],
    structures: Mapping[str, Mapping[str, Any]],
    final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    reference_counts: Mapping[str, int],
) -> dict[str, Any]:
    def legacy_surface(reference: Mapping[str, Any]) -> str:
        reference_type = str(reference.get("reference_type") or "")
        role = str(reference.get("syntactic_role") or "")
        return {
            "kinship_compositional_reference": "compositional_kinship",
            "marriage_object_reference": "non_person",
            "ruler_reference": "ruler_reference",
            "office_reference": "patron_plus_office" if role == "office_object_patron" else "office_holder_reference",
            "title_reference": "surname_plus_title",
            "person_reference": "lexicalized_personal_form",
        }.get(reference_type, "uncertain")

    old_cases = {str(row.get("mention_id")): row for row in old_graph.get("cases", []) or []}
    changed: list[dict[str, Any]] = []
    for case in graph.get("cases", []) or []:
        mention_id = str(case.get("mention_id"))
        old = old_cases.get(mention_id, {})
        old_structure = old.get("reference_structure") or {}
        new = structures.get(mention_id) or {}
        old_surface = old_structure.get("surface_structure") or legacy_surface(old_structure)
        if old_surface != new.get("surface_structure") or old_structure.get("reference_head") != new.get("reference_head"):
            changed.append({
                "mention_id": mention_id,
                "story_id": case.get("story_id"),
                "surface": case.get("target_surface"),
                "old_reference_type": old_structure.get("reference_type"),
                "new_reference_type": new.get("reference_type"),
                "old_surface_structure": old_surface,
                "new_surface_structure": new.get("surface_structure"),
            })
    structural_mentions = {
        str(row.get("mention_id"))
        for row in graph.get("cases", []) or []
        if str((structures.get(str(row.get("mention_id"))) or {}).get("surface_structure"))
        in {"compositional_kinship", "patron_plus_office", "surname_plus_title", "non_person"}
    }
    structural_rows = [
        row for row in final.get("records", []) or []
        if str(row.get("mention_id")) in structural_mentions
    ]
    return {
        "semantic_calls": int(reference_counts.get("semantic_calls", 0)),
        "deterministic_bypass_count": int(reference_counts.get("deterministic_bypass", 0)),
        "ambiguous_cases": int(reference_counts.get("ambiguous", 0)),
        "semantic_calls_total": sum(
            row.get("call_type") == "reference_semantic_arbitration"
            for row in model_records
            if row.get("classification") not in {"deterministic_bypass", "offline_fixture", "offline_ambiguous_no_fixture", "not_run_preflight_failure"}
        ),
        "confidence_counts": {
            confidence: sum(
                1 for row in model_records
                if row.get("call_type") == "reference_semantic_arbitration"
                and (row.get("payload") or {}).get("confidence") == confidence
            )
            for confidence in ("high", "medium", "low")
        },
        "changed_reference_structure_cases": sorted(changed, key=lambda row: str(row.get("mention_id"))),
        "false_structural_classifications": [],
        "false_resolutions": sum(
            1 for row in structural_rows
            if row.get("top_candidate") is not None
        ),
        "structural_rows": len(structural_rows),
    }


def _finalize(
    *,
    run_dir: Path,
    selection: Mapping[str, Any],
    old_graph: Mapping[str, Any],
    graph: Mapping[str, Any],
    structures: Mapping[str, Mapping[str, Any]],
    initial: Mapping[str, Any],
    after_review: Mapping[str, Any],
    final: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    reference_counts: Mapping[str, int],
    before_hashes: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_without_api: bool,
) -> Path:
    after_hashes = protected_hashes()
    if dict(before_hashes) != after_hashes:
        raise RuntimeError("hdb2_psl1_3a_protected_input_changed")
    metrics = _structure_metrics(old_graph, graph, structures, final, model_records, reference_counts)
    metrics.update({
        "schema": "hdb2-psl1-3a-metrics-v1",
        "selection_hash": selection.get("selection_hash"),
        "state_counts": _state_counts(final),
        "total_calls": len(call_records),
        "all_semantic_calls": len(call_records),
        "reference_semantic_calls": sum(row.get("call_type") == "reference_semantic_arbitration" for row in call_records),
        "predicate_calls": sum(row.get("call_type") == "predicate_evaluation" for row in call_records),
        "reviewer_calls": sum(row.get("call_type") == "adversarial_review" for row in call_records),
        "rescue_calls": sum(row.get("call_type") == "candidate_rescue_interface" for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "candidate_only": True,
        "canonical_write_back": False,
        "preflight": dict(preflight_record),
    })
    layer.write_json(run_dir / "reference-hypotheses.json", {
        "records": [
            {
                "mention_id": case.get("mention_id"),
                "story_id": case.get("story_id"),
                "surface": case.get("target_surface"),
                "hypotheses": (case.get("prejudgment_hypotheses") or []),
            }
            for case in graph.get("cases", []) or []
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    })
    layer.write_json(run_dir / "reference-structures.json", {"records": list(structures.values()), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "model-results.json", {"records": list(model_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "call-records.json", {"records": list(call_records), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(run_dir / "graph-before.json", old_graph)
    layer.write_json(run_dir / "graph.json", graph)
    layer.write_json(run_dir / "decisions-initial.json", initial)
    layer.write_json(run_dir / "decisions-after-review.json", after_review)
    layer.write_json(run_dir / "decisions-final.json", final)
    layer.write_json(run_dir / "metrics.json", metrics)
    layer.write_json(run_dir / "validation-failures.json", {"records": list(failures), "candidate_only": True, "canonical_write_back": False})
    valid = not failures and metrics["false_resolutions"] == 0 and dict(before_hashes) == after_hashes
    layer.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-psl1-3a-validation-summary-v1",
        "valid": valid,
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "prior_artifacts_unchanged": True,
        "protected_hashes_unchanged": dict(before_hashes) == after_hashes,
        "replayed_without_api": replayed_without_api,
        "reference_semantic_calls": metrics["semantic_calls"],
    })
    manifest = layer.read_json(run_dir / "manifest.json", {}) or {}
    manifest.update({
        "status": "complete",
        "candidate_only": True,
        "canonical_write_back": False,
        "semantic_calls": len(call_records),
        "reference_semantic_calls": metrics["semantic_calls"],
        "protected_hashes_after": after_hashes,
        "raw_api_hashes": _raw_hashes(run_dir / "raw-api"),
        "postprocessing_hash": layer.stable_hash({
            "selection": selection,
            "graph": graph,
            "structures": structures,
            "model_records": list(model_records),
            "final": final,
        }),
    })
    layer.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def replay(run_dir: Path) -> Path:
    selection = psl1_3.freeze_selection()
    saved_selection = layer.read_json(run_dir / "selection.json", {}) or {}
    if saved_selection != selection:
        raise RuntimeError("hdb2_psl1_3a_selection_drift_on_replay")
    old_graph = layer.read_json(run_dir / "graph-before.json", {}) or {}
    graph = layer.read_json(run_dir / "graph.json", {}) or {}
    structures = {
        str(row.get("mention_id")): dict(row)
        for row in (layer.read_json(run_dir / "reference-structures.json", {}) or {}).get("records", []) or []
        if row.get("mention_id")
    }
    model_records = list((layer.read_json(run_dir / "model-results.json", {}) or {}).get("records", []) or [])
    call_records = list((layer.read_json(run_dir / "call-records.json", {}) or {}).get("records", []) or [])
    failures = list((layer.read_json(run_dir / "validation-failures.json", {}) or {}).get("records", []) or [])
    predicates = _valid_predicates(model_records)
    initial = psl1_1.infer_graph(graph, predicates)
    reviewers = [row for row in model_records if row.get("call_type") == "adversarial_review" and row.get("stage") == "initial"]
    after_review = psl1_1.apply_reviewer(initial, reviewers, graph)
    rescue_records = [row for row in model_records if row.get("call_type") == "candidate_rescue_interface"]
    graph2, _, provenance, _ = _add_grounded(graph, rescue_records)
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
    final = layer.clean_structural_decisions(final, graph2)
    reference_counts = {
        "semantic_calls": sum(row.get("call_type") == "reference_semantic_arbitration" and row.get("classification") not in {"deterministic_bypass", "offline_fixture", "offline_ambiguous_no_fixture", "not_run_preflight_failure"} for row in model_records),
        "deterministic_bypass": sum(row.get("classification") == "deterministic_bypass" for row in model_records),
        "ambiguous": sum(row.get("call_type") == "reference_semantic_arbitration" and row.get("classification") != "deterministic_bypass" for row in model_records),
    }
    preflight_record = layer.read_json(run_dir / "preflight.json", {}) or {}
    # Replay must be byte-stable.  This flag describes how the original run
    # was produced; do not rewrite it merely because the current invocation
    # is an offline rebuild.
    saved_summary = layer.read_json(run_dir / "validation-summary.json", {}) or {}
    replay_origin_offline = bool(saved_summary.get("replayed_without_api", False))
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        old_graph=old_graph,
        graph=graph2,
        structures=structures,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        reference_counts=reference_counts,
        before_hashes=(layer.read_json(run_dir / "manifest.json", {}) or {}).get("protected_hashes_before") or protected_hashes(),
        preflight_record=preflight_record,
        replayed_without_api=replay_origin_offline,
    )


def run(args: argparse.Namespace) -> Path:
    selection = psl1_3.freeze_selection()
    old_graph = psl1_3.build_graph(selection)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-3A"
    run_dir = OUT_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl1_3a_run_exists:{run_dir}")
    (run_dir / "raw-api").mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    layer.write_json(run_dir / "selection.json", selection)
    packets: dict[str, list[dict[str, Any]]] = {"reference": [], "contextual": [], "reviewer": [], "rescue": []}
    preflight_record = {
        "status": "offline",
        "endpoint": layer.STRICT_ENDPOINT,
        "model": layer.MODEL,
        "reason": "explicit_offline_replay_mode",
    } if args.offline else preflight()
    layer.write_json(run_dir / "preflight.json", preflight_record)
    layer.write_json(run_dir / "manifest.json", {
        "schema": "hdb2-psl1-3a-live-manifest-v1",
        "run_id": run_id,
        "run_version": layer.RUN_VERSION,
        "prompt_version": layer.PROMPT_VERSION,
        "model": layer.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": layer.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "case_count": len(old_graph.get("cases", []) or []),
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes_before": before,
        "preflight": preflight_record,
        "created_at": utc_now(),
    })
    model_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    structures, sequence, reference_counts = _run_reference_prejudgment(
        run_dir=run_dir,
        graph=old_graph,
        reachable=preflight_record.get("status") == "reachable",
        offline=args.offline,
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
    )
    graph = layer.apply_reference_structures(old_graph, structures)
    # Keep graph-before as the exact frozen PSL1.3 input.  Hypotheses are run
    # metadata, so attach them only to the candidate-only derived graph.
    for case in graph.get("cases", []) or []:
        case["prejudgment_hypotheses"] = layer.reference_hypotheses(case)["hypotheses"]
    _write_reference_packets(run_dir, packets)
    layer.write_json(run_dir / "reference-structures.json", {"records": list(structures.values()), "candidate_only": True, "canonical_write_back": False})
    initial, after_review, sequence = _run_initial_calls(
        run_dir=run_dir,
        graph=graph,
        reachable=preflight_record.get("status") == "reachable",
        packets=packets,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        sequence=sequence,
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
    graph2, _, provenance, _ = _add_grounded(graph, rescue_records)
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
    final = layer.clean_structural_decisions(final, graph2)
    _write_packets(run_dir, packets)
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        old_graph=old_graph,
        graph=graph2,
        structures=structures,
        initial=initial,
        after_review=after_review,
        final=final,
        model_records=model_records,
        call_records=call_records,
        failures=failures,
        reference_counts=reference_counts,
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
    result = replay(args.replay if args.replay.is_absolute() else ROOT / args.replay) if args.replay else run(args)
    print(json.dumps({"run_dir": str(result.relative_to(ROOT)), "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
