#!/usr/bin/env python3
"""Validate the additive HDB2-PSL1.2 candidate-rescue pilot.

The validator is intentionally independent of the provider.  It checks the
frozen twelve-occurrence selection, the closed rescue tool contract, exact
packet/model provenance, and that invalid rescue diagnostics never alter the
candidate-only result.  It does not write canonical or reviewed data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_2_common as layer  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402


def _load(path: Path, default: Any = None) -> Any:
    return layer.read_json(path, default)


def _fail(errors: list[str], value: str) -> None:
    errors.append(value)


def _validate_selection(selection: Mapping[str, Any], errors: list[str]) -> None:
    if selection.get("schema") != "hdb2-psl1-2-selection-v1":
        _fail(errors, "selection_schema_invalid")
    rows = list(selection.get("independent_cases", []) or [])
    if selection.get("independent_count") != 12 or len(rows) != 12:
        _fail(errors, "selection_count_invalid")
    if selection.get("frozen_before_live") is not True:
        _fail(errors, "selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        _fail(errors, "selection_safety_flags_invalid")
    ids = [str(row.get("occurrence_id") or "") for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        _fail(errors, "selection_occurrence_ids_invalid")
    excluded = {str(value) for value in selection.get("excluded_previous_occurrence_ids", []) if value}
    if set(ids) & excluded:
        _fail(errors, "selection_previous_overlap")
    expected = layer.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected:
        _fail(errors, "selection_hash_invalid")
    # Recompute only from the current frozen input.  The comparison is a
    # useful guard against a changed review projection or selection policy.
    try:
        rebuilt = layer.build_selection(layer.SELECTION_PATH)
    except Exception as exc:  # pragma: no cover - surfaced as a validation error
        _fail(errors, f"selection_rebuild_failed:{type(exc).__name__}:{exc}")
    else:
        if rebuilt != dict(selection):
            _fail(errors, "selection_rebuild_drift")
    for row in rows:
        if not row.get("source_refs"):
            _fail(errors, f"selection_source_refs_empty:{row.get('occurrence_id')}")


def _validate_graph(graph: Mapping[str, Any], errors: list[str]) -> None:
    if graph.get("candidate_only") is not True or graph.get("canonical_write_back") is not False:
        _fail(errors, "graph_safety_flags_invalid")
    seen: set[str] = set()
    for case in graph.get("cases", []) or []:
        occurrence_id = str(case.get("occurrence_id") or "")
        if not occurrence_id or occurrence_id in seen:
            _fail(errors, f"graph_occurrence_invalid:{occurrence_id}")
        seen.add(occurrence_id)
        candidate_keys = {str(row.get("candidate_key")) for row in case.get("candidates", []) or []}
        indexed = {str(value) for value in case.get("candidate_keys", []) or []}
        if candidate_keys != indexed:
            _fail(errors, f"candidate_key_index_invalid:{occurrence_id}")
        for candidate in case.get("candidates", []) or []:
            if not candidate.get("display_name"):
                _fail(errors, f"candidate_display_empty:{occurrence_id}")
            if candidate.get("person_id") is None and not str(candidate.get("candidate_node_id") or "").startswith("local:"):
                # Ruler nodes are a frozen PSL1 exception; rescue-created
                # no-ID candidates must always be local candidate nodes.
                node = str(candidate.get("candidate_node_id") or "")
                if not node.startswith("ruler:"):
                    _fail(errors, f"no_id_candidate_not_local:{occurrence_id}:{candidate.get('candidate_key')}")


def _packets(run_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for filename in ("prompt-packets.json", "reviewer-packets.json", "rescue-packets.json"):
        document = _load(run_dir / filename, {}) or {}
        for row in document.get("records", []) or []:
            key = str(row.get("key") or "")
            if key:
                result[key] = row.get("packet") or {}
    return result


def _validate_packets(packets: Mapping[str, Mapping[str, Any]], errors: list[str]) -> None:
    for key, packet in packets.items():
        if packet.get("candidate_only") is not True or packet.get("canonical_write_back") is not False:
            _fail(errors, f"packet_safety_flags_invalid:{key}")
        forbidden = layer._walk_keys(packet)
        if forbidden:
            _fail(errors, f"provider_id_in_packet:{key}:{','.join(sorted(forbidden))}")
        # Rescue packets must contain the diagnostic task boundary, but must
        # not contain provider identity IDs through an accidental nested field.
        if key.startswith("rescue:") and packet.get("task") != "diagnose whether the supplied candidate set is missing a grounded historical entity":
            _fail(errors, f"rescue_task_invalid:{key}")


def _validate_model_records(run_dir: Path, errors: list[str]) -> tuple[set[str], set[str]]:
    packets = _packets(run_dir)
    _validate_packets(packets, errors)
    document = _load(run_dir / "model-results.json", {}) or {}
    invalid_rescue_mentions: set[str] = set()
    invalid_records: set[str] = set()
    for row in document.get("records", []) or []:
        classification = str(row.get("classification") or "")
        if classification in {"no_call", "not_run_preflight_failure", "frozen_replay"}:
            continue
        packet_key = str(row.get("packet_key") or "")
        packet = packets.get(packet_key)
        if packet is None:
            _fail(errors, f"saved_packet_missing:{packet_key}")
            continue
        call_type = str(row.get("call_type") or "")
        if call_type == "candidate_rescue_diagnosis":
            validation = layer.validate_rescue_diagnosis(row.get("payload") or {}, packet)
        elif call_type == "adversarial_review":
            validation = psl1.validate_reviewer(row.get("payload") or {}, packet)
        elif call_type == "predicate_evaluation":
            validation = psl1.validate_predicates(row.get("payload") or {}, packet)
        else:
            _fail(errors, f"call_type_invalid:{call_type}")
            continue
        if validation.get("valid") is not True:
            mention = str(row.get("mention_id") or "")
            invalid_records.add(mention)
            if call_type == "candidate_rescue_diagnosis":
                invalid_rescue_mentions.add(mention)
    return invalid_rescue_mentions, invalid_records


def _validate_run(run_dir: Path, selection: Mapping[str, Any], errors: list[str]) -> dict[str, Any]:
    manifest = _load(run_dir / "manifest.json", {}) or {}
    if not manifest:
        _fail(errors, "manifest_missing")
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        _fail(errors, "run_selection_hash_mismatch")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        _fail(errors, "manifest_safety_flags_invalid")
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        _fail(errors, "protected_hashes_changed")
    invalid_rescue_mentions, invalid_records = _validate_model_records(run_dir, errors)
    provenance = list((_load(run_dir / "rescue-candidates.json", {}) or {}).get("records", []) or [])
    mutated_invalid = sorted(
        invalid_rescue_mentions & {str(row.get("mention_id") or "") for row in provenance}
    )
    if mutated_invalid:
        _fail(errors, f"invalid_rescue_payload_mutated_state:{','.join(mutated_invalid)}")
    metrics = _load(run_dir / "metrics.json", {}) or {}
    if metrics.get("invalid_rescue_payload_mutations") not in (0, None):
        _fail(errors, "invalid_rescue_payload_mutations")
    summary = _load(run_dir / "validation-summary.json", {}) or {}
    if summary.get("candidate_only") is not True or summary.get("canonical_write_back") is not False:
        _fail(errors, "summary_safety_flags_invalid")
    if summary.get("protected_hashes_unchanged") is not True:
        _fail(errors, "summary_protected_hashes_changed")
    required = _load(run_dir / "required-regressions.json", {}) or {}
    false_cases = _load(run_dir / "false-resolution-regressions.json", {}) or {}
    if required.get("all_pass") is not True:
        _fail(errors, "required_regression_failed")
    if false_cases.get("all_pass") is not True:
        _fail(errors, "false_resolution_regression_failed")
    final = _load(run_dir / "decisions-final.json", {}) or {}
    if final.get("candidate_only") is not True or final.get("canonical_write_back") is not False:
        _fail(errors, "final_safety_flags_invalid")
    audit = _load(run_dir / "rescue-audit.json", {}) or {}
    if audit.get("schema") != "hdb2-psl1-2-rescue-audit-v1":
        _fail(errors, "rescue_audit_schema_invalid")
    elif len(audit.get("records", []) or []) != len(selection.get("independent_cases", []) or []):
        _fail(errors, "rescue_audit_count_invalid")
    if audit and (audit.get("candidate_only") is not True or audit.get("canonical_write_back") is not False):
        _fail(errors, "rescue_audit_safety_flags_invalid")
    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "model_records": len((_load(run_dir / "model-results.json", {}) or {}).get("records", []) or []),
        "invalid_model_records": len(invalid_records),
        "rescue_audit_records": len(audit.get("records", []) or []),
        "metrics": metrics,
    }


def validate(run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    selection = _load(layer.SELECTION_PATH, {}) or {}
    _validate_selection(selection, errors)
    required = layer.required_regression_records()
    false_cases = layer.false_resolution_regression()
    if required.get("all_pass") is not True:
        _fail(errors, "offline_required_regression_failed")
    if false_cases.get("all_pass") is not True:
        _fail(errors, "offline_false_resolution_regression_failed")
    details: dict[str, Any] = {
        "selection_count": len(selection.get("independent_cases", []) or []),
        "required_regressions": required,
        "false_resolution_regressions": false_cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    if run_dir is not None:
        details.update(_validate_run(run_dir, selection, errors))
    return {"valid": not errors, "errors": sorted(set(errors)), **details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir
    if run_dir and not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    result = validate(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
