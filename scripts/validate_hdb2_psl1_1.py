#!/usr/bin/env python3
"""Validate HDB2-PSL1.1 artifacts without making historical decisions."""

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

import hdb2_psl1_1_common as layer  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
import run_hdb2_psl1_1 as runner  # noqa: E402


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _fail(message: str) -> None:
    raise RuntimeError(message)


def _validate_selection(selection: Mapping[str, Any]) -> None:
    if selection.get("schema") != "hdb2-psl1-1-selection-v1":
        _fail("selection_schema_invalid")
    if selection.get("independent_count") != 10 or len(selection.get("independent_cases", [])) != 10:
        _fail("independent_selection_count_invalid")
    if selection.get("frozen_before_live") is not True:
        _fail("selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        _fail("selection_safety_flags_invalid")
    occurrence_ids = [str(row.get("occurrence_id")) for row in selection.get("independent_cases", [])]
    if len(set(occurrence_ids)) != 10 or any(value in {"", "None"} for value in occurrence_ids):
        _fail("independent_occurrence_ids_invalid")
    psl1_ids = set(str(value) for value in selection.get("excluded_psl1_occurrence_ids", []))
    if psl1_ids & set(occurrence_ids):
        _fail("independent_psl1_overlap")
    if set(str(value) for value in selection.get("development_occurrence_ids", [])) & set(occurrence_ids):
        _fail("independent_development_overlap")
    expected_hash = layer.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected_hash:
        _fail("selection_hash_invalid")
    for row in selection.get("independent_cases", []):
        if not row.get("candidate_set"):
            _fail(f"candidate_set_empty:{row.get('occurrence_id')}")
        if not row.get("source_refs"):
            _fail(f"source_refs_empty:{row.get('occurrence_id')}")


def _validate_graph(graph: Mapping[str, Any], *, label: str) -> None:
    if graph.get("candidate_only") is not True or graph.get("canonical_write_back") is not False:
        _fail(f"{label}:graph_safety_flags_invalid")
    seen: set[str] = set()
    for case in graph.get("cases", []):
        mention_id = str(case.get("mention_id"))
        if not mention_id or mention_id in seen:
            _fail(f"{label}:mention_id_invalid_or_duplicate:{mention_id}")
        seen.add(mention_id)
        structure = case.get("reference_structure")
        if not isinstance(structure, Mapping):
            _fail(f"{label}:reference_structure_missing:{mention_id}")
        keys = {str(row.get("candidate_key")) for row in case.get("candidates", [])}
        if not keys.issubset(set(str(value) for value in case.get("candidate_keys", []))):
            _fail(f"{label}:candidate_key_index_invalid:{mention_id}")
        for packet_key in ("candidates", "candidate_keys"):
            for value in case.get(packet_key, []) if packet_key == "candidate_keys" else []:
                if packet_key == "candidate_keys" and value is None:
                    _fail(f"{label}:null_candidate_key:{mention_id}")


def _validate_packets(run_dir: Path) -> None:
    documents = [read_json(run_dir / "prompt-packets.json", {}) or {}, read_json(run_dir / "reviewer-packets.json", {}) or {}]
    for document in documents:
        for row in document.get("records", []):
            packet = row.get("packet") or {}
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            if "person_id" in rendered or "candidate_id" in rendered:
                _fail(f"provider_id_in_packet:{row.get('key')}")
            if packet.get("candidate_only") is not True or packet.get("canonical_write_back") is not False:
                _fail(f"packet_safety_flags_invalid:{row.get('key')}")


def _validate_run(run_dir: Path, selection: Mapping[str, Any]) -> dict[str, Any]:
    manifest = read_json(run_dir / "manifest.json", {}) or {}
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        _fail("run_selection_hash_mismatch")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        _fail("run_safety_flags_invalid")
    _validate_packets(run_dir)
    packets: dict[str, dict[str, Any]] = {}
    for filename in ("prompt-packets.json", "reviewer-packets.json"):
        document = read_json(run_dir / filename, {}) or {}
        packets.update({str(row.get("key")): row.get("packet") or {} for row in document.get("records", [])})
    model_rows = list((read_json(run_dir / "model-results.json", {}) or {}).get("records", []))
    payload_rejections: list[dict[str, Any]] = []
    for row in model_rows:
        if row.get("classification") == "frozen_replay":
            continue
        mention_id = row.get("mention_id")
        key = f"review:{mention_id}" if row.get("call_type") == "adversarial_review" else f"predicate:{mention_id}"
        packet = packets.get(key)
        if packet is None:
            _fail(f"saved_packet_missing:{key}")
        validation = (
            psl1.validate_reviewer(row.get("payload") or {}, packet)
            if row.get("call_type") == "adversarial_review"
            else psl1.validate_predicates(row.get("payload") or {}, packet)
        )
        if validation.get("valid") is not True:
            payload_rejections.append({
                "mention_id": mention_id,
                "call_type": row.get("call_type"),
                "errors": list(validation.get("errors", [])),
            })
    summary = read_json(run_dir / "validation-summary.json", {}) or {}
    if summary.get("candidate_only") is not True or summary.get("canonical_write_back") is not False:
        _fail("summary_safety_flags_invalid")
    if summary.get("protected_hashes_unchanged") is not True:
        _fail("protected_hashes_changed")
    metrics = read_json(run_dir / "metrics.json", {}) or {}
    safety = read_json(run_dir / "safety.json", {}) or {}
    if any(int(safety.get(key) or 0) for key in (
        "same_surface_automatic_merges",
        "compositional_base_person_collapses",
        "nonperson_person_id_anomalies",
        "non_identity_self_relations",
        "hard_veto_promotions",
        "invalid_candidate_keys",
        "invalid_evidence_references",
        "confidence_only_resolutions",
    )):
        _fail("safety_metric_nonzero")
    # A provider payload can be rejected (notably the literal string
    # ``"null"`` for an optional candidate key).  That is reported as an
    # audit diagnostic, not a state-integrity failure, because rejected rows
    # are never passed to inference.
    independent_audit = read_json(run_dir / "independent-audit.json", {}) or {}
    if len(independent_audit.get("records", [])) != 10:
        _fail("independent_audit_count_invalid")
    final_rows = [
        row
        for filename in ("decisions-final-development.json", "decisions-final-independent.json")
        for row in (read_json(run_dir / filename, {}) or {}).get("records", [])
    ]
    reviewer_mutations = {
        str(row.get("mention_id"))
        for row in final_rows
        if row.get("reviewer_resolved")
    }
    for rejection in payload_rejections:
        if str(rejection.get("mention_id")) in reviewer_mutations:
            _fail(f"invalid_payload_mutated_state:{rejection.get('mention_id')}")
    required = read_json(run_dir / "required-development-outcomes.json", {}) or {}
    if required.get("all_required_pass") is not True:
        _fail("development_required_outcome_failed")
    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "summary_valid": summary.get("valid"),
        "payload_validation_failures": len(payload_rejections),
        "metrics": metrics,
        "safety": safety,
    }


def validate(run_dir: Path | None = None) -> dict[str, Any]:
    selection = read_json(layer.SELECTION_PATH, {}) or {}
    _validate_selection(selection)
    development_graphs = layer.load_psl1_graphs()
    _validate_graph(development_graphs[0], label="development_regression")
    _validate_graph(development_graphs[1], label="development_holdout")
    if run_dir is None:
        return {
            "valid": True,
            "selection_hash": selection.get("selection_hash"),
            "independent_count": selection.get("independent_count"),
            "development_counts": [len(graph.get("cases", [])) for graph in development_graphs],
            "offline_development": True,
            "candidate_only": True,
            "canonical_write_back": False,
        }
    details = _validate_run(run_dir, selection)
    return {"valid": bool(details.get("summary_valid")), **details}


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
