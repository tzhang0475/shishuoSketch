#!/usr/bin/env python3
"""Validate the candidate-only HDB2-PSL1 experiment.

This validator checks the frozen selection, closed predicate contract,
fail-closed model validation, the explicit 02-yanyu-054 distinctness
regression, and protected-input hashes.  It never writes historical data.
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

import hdb2_psl1_common as common  # noqa: E402


def _load(path: Path, default: Any = None) -> Any:
    return common.read_json(path, default)


def _forbidden_rendered(value: Any) -> list[str]:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return [key for key in common.FORBIDDEN_ID_KEYS if key in rendered]


def validate(selection: Mapping[str, Any], graph_regression: Mapping[str, Any], graph_holdout: Mapping[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    regression_rows = list(selection.get("regression_cases", []))
    holdout_rows = list(selection.get("holdout_cases", []))
    if selection.get("schema") != "hdb2-psl1-selection-v1":
        errors.append("selection_schema_invalid")
    if len(regression_rows) != 24:
        errors.append("regression_count_invalid")
    if len(holdout_rows) != 20:
        errors.append("holdout_count_invalid")
    expected_selection_hash = common.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected_selection_hash:
        errors.append("selection_hash_invalid")
    if selection.get("frozen_before_live") is not True:
        errors.append("selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("selection_projection_flags_invalid")
    regression_ids = {str(row.get("occurrence_id")) for row in regression_rows}
    holdout_ids = {str(row.get("occurrence_id")) for row in holdout_rows}
    if len(regression_ids) != len(regression_rows) or len(holdout_ids) != len(holdout_rows):
        errors.append("selection_occurrence_ids_not_unique")
    if regression_ids & holdout_ids:
        errors.append("regression_holdout_overlap")
    psl0_selection = _load(common.PSL0_SELECTION, {}) or {}
    psl0_ids = {str(row.get("occurrence_id")) for row in psl0_selection.get("cases", [])}
    if holdout_ids & psl0_ids:
        errors.append("holdout_psl0_overlap")
    if selection.get("regression_selection_hash") != psl0_selection.get("selection_hash"):
        errors.append("regression_source_hash_changed")
    if selection.get("holdout_selection_hash") != common.stable_hash({
        key: value for key, value in (_load(common.HOLDOUT_SELECTION, {}) or {}).items() if key != "selection_hash"
    }):
        errors.append("holdout_source_hash_invalid")
    for graph, expected in ((graph_regression, 24), (graph_holdout, 20)):
        cases = list(graph.get("cases", []))
        if len(cases) != expected:
            errors.append(f"graph_case_count_invalid:{expected}:{len(cases)}")
        if graph.get("candidate_only") is not True or graph.get("canonical_write_back") is not False:
            errors.append("graph_projection_flags_invalid")
        if set(graph.get("predicate_set", [])) & {"ContextCompatible", "CrossStoryCompatible"}:
            errors.append("obsolete_positive_predicate_present")
        for case in cases:
            if _forbidden_rendered(common.wire_packet(case, cases, graph)):
                errors.append(f"forbidden_id_in_packet:{case.get('mention_id')}")
            for candidate in case.get("candidates", []):
                if candidate.get("person_id") is None:
                    node = str(candidate.get("candidate_node_id") or "")
                    if not node.startswith(("local:", "ruler:")):
                        errors.append(f"no_id_candidate_not_local:{case.get('mention_id')}:{candidate.get('candidate_key')}")
    distinct = list(graph_regression.get("distinct_pairs", []))
    yanyu = [row for row in graph_regression.get("cases", []) if str(row.get("story_id")) == "02-yanyu-054"]
    if not any({str(row.get("target_surface")) for row in yanyu} >= {"王長史", "劉尹"} for _ in [0]):
        errors.append("yanyu_distinct_inputs_missing")
    if not any({str(row.get("left_mention_id")), str(row.get("right_mention_id"))} <= {str(row.get("mention_id")) for row in yanyu} for row in distinct):
        errors.append("yanyu_distinct_pair_missing")
    tool = common.predicate_tool()["function"]
    if tool.get("strict") is not True:
        errors.append("predicate_tool_not_strict")
    params = tool.get("parameters", {})
    if params.get("additionalProperties") is not False or set(params.get("required", [])) != set(params.get("properties", {})):
        errors.append("predicate_tool_closed_contract_invalid")
    review_tool = common.reviewer_tool()["function"]
    if review_tool.get("strict") is not True:
        errors.append("reviewer_tool_not_strict")
    review_params = review_tool.get("parameters", {})
    if review_params.get("additionalProperties") is not False or set(review_params.get("required", [])) != set(review_params.get("properties", {})):
        errors.append("reviewer_tool_closed_contract_invalid")

    summary: dict[str, Any] = {
        "selection_count": len(regression_rows) + len(holdout_rows),
        "regression_count": len(regression_rows),
        "holdout_count": len(holdout_rows),
    }
    if run_dir is not None:
        manifest = _load(run_dir / "manifest.json", {}) or {}
        if not manifest:
            errors.append("manifest_missing")
        if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
            errors.append("manifest_projection_flags_invalid")
        if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
            errors.append("protected_hashes_changed")
        packets: dict[str, Any] = {}
        for filename in ("prompt-packets.json", "reviewer-packets.json"):
            document = _load(run_dir / filename, {}) or {}
            for row in document.get("records", []):
                packets[str(row.get("key"))] = row.get("packet") or {}
                if _forbidden_rendered(row.get("packet") or {}):
                    errors.append(f"forbidden_id_in_saved_packet:{row.get('key')}")
                rendered = json.dumps(row.get("packet") or {}, ensure_ascii=False, sort_keys=True)
                if "ContextCompatible" in rendered or "CrossStoryCompatible" in rendered:
                    errors.append(f"obsolete_predicate_in_saved_packet:{row.get('key')}")
        model_document = _load(run_dir / "model-predicate-results.json", {}) or {}
        model_rows = list(model_document.get("records", []))
        for row in model_rows:
            key = f"review:{row.get('mention_id')}" if row.get("call_type") == "adversarial_review" else f"predicate:{row.get('mention_id')}"
            packet = packets.get(key)
            if packet is None:
                errors.append(f"saved_packet_missing:{key}")
                continue
            if row.get("classification") == "no_call":
                continue
            result = common.validate_reviewer(row.get("payload") or {}, packet) if row.get("call_type") == "adversarial_review" else common.validate_predicates(row.get("payload") or {}, packet)
            if result.get("valid") is not True:
                errors.extend(f"{key}:{error}" for error in result.get("errors", []))
        for filename, expected in (("decisions-final-regression.json", 24), ("decisions-final-holdout.json", 20)):
            decisions = _load(run_dir / filename, {}) or {}
            rows = list(decisions.get("records", []))
            if len(rows) != expected:
                errors.append(f"decision_count_invalid:{filename}")
            if decisions.get("candidate_only") is not True or decisions.get("canonical_write_back") is not False:
                errors.append(f"decision_projection_flags_invalid:{filename}")
            for row in rows:
                for ranking in row.get("candidate_rankings", []):
                    value = ranking.get("link")
                    if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                        errors.append(f"link_out_of_range:{row.get('mention_id')}:{ranking.get('candidate_key')}")
                if row.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
                    top = next((item for item in row.get("candidate_rankings", []) if item.get("candidate_key") == row.get("top_candidate_key")), {})
                    if top.get("hard_conflict"):
                        errors.append(f"hard_veto_promotion:{row.get('mention_id')}")
        safety = _load(run_dir / "safety.json", {}) or {}
        for key in (
            "same_surface_automatic_merges",
            "compositional_base_person_collapses",
            "nonperson_person_id_anomalies",
            "non_identity_self_relations",
            "hard_veto_promotions",
            "invalid_candidate_keys",
            "invalid_evidence_references",
            "confidence_only_resolutions",
        ):
            if safety.get(key) != 0:
                errors.append(f"safety_metric_nonzero:{key}")
        if (_load(run_dir / "metrics.json", {}) or {}).get("coreference_pair_conflicts", 0):
            errors.append("coreference_pair_conflicts_present")
        summary.update({
            "model_records": len(model_rows),
            "packet_count": len(packets),
            "status": manifest.get("status"),
            "validation_failures": len(_load(run_dir / "validation-failures.json", {}).get("records", [])),
        })
    return {"valid": not errors, "errors": sorted(set(errors)), **summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    selection = _load(common.ANNOTATION / "hdb2-psl1-selection.json", {}) or {}
    regression = common.build_graph_cases(common.load_regression_cases())
    holdout = common.build_graph_cases(common.load_holdout_cases({"holdout_cases": selection.get("holdout_cases", [])}))
    run_dir = args.run_dir
    if run_dir and not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    result = validate(selection, regression, holdout, run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
