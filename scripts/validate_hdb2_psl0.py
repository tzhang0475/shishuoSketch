#!/usr/bin/env python3
"""Validate the isolated HDB2-PSL0 experiment and its candidate-only output."""

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

import hdb2_psl0_common as common  # noqa: E402


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(selection: Mapping[str, Any], graph: Mapping[str, Any] | None = None, run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    rows = list(selection.get("cases", []))
    source = common.read_json(common.LJ0_SELECTION, {}) or {}
    if len(rows) != 24:
        errors.append("selection_count_invalid")
    if selection.get("source_selection_hash") != source.get("selection_hash"):
        errors.append("source_selection_hash_changed")
    if selection.get("selection_hash") != common.stable_hash(rows):
        errors.append("selection_hash_invalid")
    if selection.get("frozen_before_live") is not True:
        errors.append("selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("selection_projection_flags_invalid")
    occurrence_ids = [str(row.get("occurrence_id")) for row in rows]
    if len(set(occurrence_ids)) != len(occurrence_ids):
        errors.append("duplicate_occurrence_ids")
    expected_ids = {str(row.get("occurrence_id")) for row in source.get("cases", [])}
    if set(occurrence_ids) != expected_ids:
        errors.append("not_same_frozen_lj0_cases")
    if graph is not None:
        cases = list(graph.get("cases", []))
        if len(cases) != len(rows):
            errors.append("graph_case_count_mismatch")
        for case in cases:
            mention_id = str(case.get("mention_id"))
            for candidate in case.get("candidates", []):
                node = str(candidate.get("candidate_node_id") or "")
                if candidate.get("person_id") is None and not node.startswith("ruler:") and not node.startswith(f"local:{mention_id}:"):
                    errors.append(f"no_id_candidate_not_occurrence_local:{mention_id}")
            packet = common_wire_for_validation(case, cases, graph)
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            for key in ("person_id", "provisional_person_id", "relation_id", "graph_id", "canonical_person_id"):
                if key in rendered:
                    errors.append(f"provider_id_in_model_packet:{mention_id}:{key}")
            tool = common.predicate_tool()["function"]
            if tool.get("strict") is not True or tool.get("parameters", {}).get("additionalProperties") is not False:
                errors.append("predicate_tool_not_strict")
            params = tool.get("parameters", {})
            if set(params.get("required", [])) != set(params.get("properties", {})):
                errors.append("predicate_tool_required_mismatch")
    run_summary: dict[str, Any] = {}
    if run_dir is not None:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            errors.append("manifest_missing")
        else:
            manifest = _load(manifest_path)
            run_summary["status"] = manifest.get("status")
            if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
                errors.append("manifest_projection_flags_invalid")
            if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
                errors.append("protected_hashes_changed")
        packets_document = _load(run_dir / "prompt-packets.json") if (run_dir / "prompt-packets.json").is_file() else {}
        packet_by_id = {str(row.get("mention_id")): row.get("packet") or {} for row in packets_document.get("records", [])}
        predicates_document = _load(run_dir / "predicate-results.json") if (run_dir / "predicate-results.json").is_file() else {}
        predicate_rows = list(predicates_document.get("records", []))
        for row in predicate_rows:
            if str(row.get("classification")) == "no_call":
                continue
            mention_id = str(row.get("mention_id"))
            packet = packet_by_id.get(mention_id)
            if packet is None:
                errors.append(f"packet_missing:{mention_id}")
                continue
            result = common.validate_predicates(row.get("payload") or {}, packet)
            if result.get("valid") is not True:
                errors.extend(f"{mention_id}:{err}" for err in result.get("errors", []))
        decisions_path = run_dir / "decisions.json"
        if decisions_path.is_file():
            decisions = _load(decisions_path)
            records = list(decisions.get("records", []))
            if len(records) != len(rows):
                errors.append("decision_count_mismatch")
            for row in records:
                if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
                    errors.append(f"decision_projection_flags_invalid:{row.get('mention_id')}")
                for ranking in row.get("candidate_rankings", []):
                    link = ranking.get("link")
                    if not isinstance(link, (int, float)) or not 0 <= float(link) <= 1:
                        errors.append(f"link_out_of_range:{row.get('mention_id')}:{ranking.get('candidate_key')}")
            run_summary["decision_count"] = len(records)
        comparison_path = run_dir / "comparison.json"
        if comparison_path.is_file():
            comparison = _load(comparison_path)
            if comparison.get("false_resolution_candidates") != 0:
                errors.append("false_resolution_candidates_nonzero")
            if comparison.get("candidate_only") is not True or comparison.get("canonical_write_back") is not False:
                errors.append("comparison_projection_flags_invalid")
            safety = comparison.get("safety_metrics") or {}
            for key in (
                "same_surface_automatic_merges",
                "compositional_base_person_collapses",
                "nonperson_person_id_anomalies",
                "hard_veto_promotions",
                "invalid_candidate_keys",
                "invalid_evidence_references",
                "confidence_only_resolutions",
            ):
                if safety.get(key) != 0:
                    errors.append(f"safety_metric_nonzero:{key}")
    return {"valid": not errors, "errors": sorted(set(errors)), "selection_count": len(rows), "run": run_summary}


def common_wire_for_validation(case: Mapping[str, Any], cases: list[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    # Kept as a tiny indirection so tests/validators use exactly the same
    # packet builder as the live runner.
    return common.wire_packet(case, cases, graph)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    selection = common.read_json(common.ANNOTATION / "hdb2-psl0-selection.json", {}) or {}
    graph = None
    run_dir = args.run_dir if args.run_dir and args.run_dir.is_absolute() else (ROOT / args.run_dir if args.run_dir else None)
    if run_dir and (run_dir / "graph-cases.json").is_file():
        graph = _load(run_dir / "graph-cases.json")
    result = validate(selection, graph, run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
