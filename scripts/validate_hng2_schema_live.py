#!/usr/bin/env python3
"""Offline validator for the HNG2-SL targeted live projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng2_schema_replay as schema_replay  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
from run_hng2_schema_live import (  # noqa: E402
    BASE,
    OUT,
    RAW,
    MODEL,
    read_json,
    json_hash,
)


class ValidationError(Exception):
    pass


OUTPUTS = (
    "selection.json", "semantic-assessments.json", "identity-recommendations.json",
    "identity-decisions.json", "search-plans.json", "retrieval-trace.json",
    "graph-actions.json",
    "updated-constraints.json", "research-gap-transitions.json", "validation-results.json",
    "metrics.json", "usage.json", "manifest.json",
)


def _canonical_false(document: Mapping[str, Any], label: str, errors: list[str]) -> None:
    if document.get("canonical_write_back") is not False:
        errors.append(f"canonical_write_back:{label}")


def _read(name: str) -> dict[str, Any]:
    value = read_json(OUT / name, None)
    if not isinstance(value, dict):
        raise ValidationError(f"missing_or_non_object:{name}")
    return value


def validate() -> list[str]:
    errors: list[str] = []
    for name in OUTPUTS:
        if not (OUT / name).is_file():
            errors.append(f"missing:{name}")
    if errors:
        return errors
    try:
        selection = _read("selection.json")
        assessments = _read("semantic-assessments.json")
        recommendations = _read("identity-recommendations.json")
        decisions = _read("identity-decisions.json")
        graph_actions = _read("graph-actions.json")
        plans = _read("search-plans.json")
        traces = _read("retrieval-trace.json")
        constraints = _read("updated-constraints.json")
        transitions = _read("research-gap-transitions.json")
        validation = _read("validation-results.json")
        metrics = _read("metrics.json")
        manifest = _read("manifest.json")
    except Exception as exc:
        return [f"read_error:{type(exc).__name__}:{exc}"]

    for label, document in (("selection", selection), ("assessments", assessments), ("recommendations", recommendations), ("decisions", decisions), ("graph-actions", graph_actions), ("plans", plans), ("traces", traces), ("constraints", constraints), ("transitions", transitions), ("validation", validation), ("usage", _read("usage.json"))):
        _canonical_false(document, label, errors)
    if selection.get("selected_case_count") != 18 or len(selection.get("live_cases", [])) != 18:
        errors.append("selection_count")
    if selection.get("open_research_gap_only") is not True:
        errors.append("selection_not_open_gap_only")
    if selection.get("no_frontier_expansion") is not True:
        errors.append("frontier_expansion_allowed")
    if manifest.get("model") != MODEL:
        errors.append("model_not_flash")
    if manifest.get("frontier_expansion") is not False or manifest.get("canonical_write_back") is not False:
        errors.append("manifest_scope")

    base_cases = read_json(BASE / "cases.json", {}) or {}
    base_gaps = read_json(BASE / "research-gaps.json", {}) or {}
    base_case_by_id = {str(row.get("case_id")): row for row in base_cases.get("cases", []) if isinstance(row, Mapping)}
    base_gap_by_id = {str(row.get("case_id")): row for row in base_gaps.get("gaps", []) if isinstance(row, Mapping)}
    selected_ids = []
    for row in selection.get("live_cases", []):
        case_id = str(row.get("case_id"))
        selected_ids.append(case_id)
        if case_id not in base_case_by_id or base_gap_by_id.get(case_id, {}).get("status") != "open":
            errors.append(f"selected_case_not_open:{case_id}")
        if str(row.get("mention_scope")) == "metatextual":
            errors.append(f"metatextual_live_case_not_allowed:{case_id}")
    if len(set(selected_ids)) != len(selected_ids):
        errors.append("duplicate_selection")
    if selection.get("actual_live_composition", {}).get("metatextual", 0):
        errors.append("metatextual_not_fixture_only")

    for row in assessments.get("assessments", []):
        if row.get("assessment_status") not in schema.ASSESSMENT_STATUSES:
            errors.append(f"assessment_status:{row.get('case_id')}:{row.get('assessment_status')}")
        if row.get("semantic_fit") not in schema.SEMANTIC_FITS:
            errors.append(f"semantic_fit:{row.get('case_id')}:{row.get('semantic_fit')}")
        if row.get("observed_role") not in schema.DISCOURSE_ROLES:
            errors.append(f"observed_role:{row.get('case_id')}:{row.get('observed_role')}")
        if (base_case_by_id.get(str(row.get("case_id")), {}).get("interpretation") or {}).get("mention_scope") == "metatextual" and row.get("observed_role") in {"event_participant", "speaker"}:
            errors.append(f"metatextual_role:{row.get('case_id')}")

    for row in recommendations.get("recommendations", []):
        if row.get("decision") not in schema.RECOMMENDATION_DECISIONS:
            errors.append(f"recommendation_decision:{row.get('case_id')}:{row.get('decision')}")
        if row.get("confidence") not in schema.CONFIDENCE_LEVELS:
            errors.append(f"recommendation_confidence:{row.get('case_id')}:{row.get('confidence')}")
        candidate_keys = {str(item.get("candidate_key")) for item in base_case_by_id.get(str(row.get("case_id")), {}).get("candidates", []) if isinstance(item, Mapping) and item.get("candidate_key")}
        if row.get("chosen_candidate_key") is not None and str(row.get("chosen_candidate_key")) not in candidate_keys:
            errors.append(f"invented_candidate_key:{row.get('case_id')}")
        if row.get("new_entity_key") not in {None, "n0"}:
            errors.append(f"invented_new_entity_key:{row.get('case_id')}")

    decision_by_id = {str(row.get("case_id")): row for row in decisions.get("decisions", []) if isinstance(row, Mapping)}
    action_by_id = {str(row.get("case_id")): row for row in graph_actions.get("actions", []) if isinstance(row, Mapping)}
    for case_id in selected_ids:
        row = decision_by_id.get(case_id)
        if not row:
            errors.append(f"missing_decision:{case_id}")
            continue
        if row.get("identity_status") not in schema.IDENTITY_STATUSES:
            errors.append(f"identity_status:{case_id}:{row.get('identity_status')}")
        if row.get("confidence") not in schema.CONFIDENCE_LEVELS:
            errors.append(f"decision_confidence:{case_id}:{row.get('confidence')}")
        if row.get("identity_status") == "resolved_new_candidate" and not row.get("new_entity_key"):
            errors.append(f"new_candidate_without_entity_key:{case_id}")
        if "provisional_person_id" in row:
            errors.append(f"identity_decision_owns_graph_id:{case_id}")
        if "graph_action" in row:
            errors.append(f"identity_decision_owns_graph_action:{case_id}")
        action = action_by_id.get(case_id, {})
        if row.get("identity_status") == "resolved_new_candidate" and not action.get("provisional_person_id"):
            errors.append(f"new_candidate_without_graph_id:{case_id}")
        if action.get("action") == "create_provisional_candidate" and action.get("node_type") != "provisional_person":
            errors.append(f"bad_graph_action:{case_id}")
        if action.get("frontier_status") in {"eligible", "candidate"} and row.get("identity_status") in {"ambiguous", "unresolved", "rejected", "not_person", "not_single_person"}:
            errors.append(f"unsafe_frontier:{case_id}")

    for row in plans.get("plans", []):
        plan = row.get("plan") if isinstance(row.get("plan"), Mapping) else {}
        if plan.get("graph_neighborhood_scope") not in {"case_only", "none"}:
            errors.append(f"recursive_search_plan:{row.get('case_id')}")
        if any(token in json.dumps(plan, ensure_ascii=False) for token in ("wave_3", "wave3", "frontier_expansion", "recursive")):
            errors.append(f"frontier_search_plan:{row.get('case_id')}")

    for row in traces.get("traces", []):
        retrieved = set(str(x) for x in row.get("retrieved_refs", []))
        opened = set(str(x) for x in row.get("opened_refs", []))
        used = set(str(x) for x in row.get("used_refs", []))
        if not opened.issubset(retrieved):
            errors.append(f"opened_not_retrieved:{row.get('case_id')}")
        if not used.issubset(opened | {str((base_case_by_id.get(str(row.get('case_id')), {}).get('observation') or {}).get('source_ref') or '')}):
            errors.append(f"used_not_opened:{row.get('case_id')}")
        if row.get("round") != 1:
            errors.append(f"retrieval_round:{row.get('case_id')}")

    for row in validation.get("results", []):
        if not isinstance(row, Mapping):
            errors.append("malformed_validation_result")
    if metrics.get("selected_cases") != 18:
        errors.append("metrics_selected_case_count")
    if metrics.get("fixture_coverage_count", 0) and metrics.get("fixture_coverage_count") == metrics.get("selected_cases"):
        errors.append("fixture_mixed_into_live_count")

    # Raw responses are allowed to contain failed model attempts, but any
    # forbidden or invalid content must have a corresponding recorded
    # validation result; raw files themselves remain immutable evidence.
    raw_root = ROOT / str(manifest.get("raw_api_root") or "")
    if not raw_root.is_dir():
        errors.append("missing_raw_api_root")
    else:
        for path in raw_root.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            if "DEEPSEEK_API_KEY" in text or "Bearer " in text:
                errors.append(f"secret_in_raw:{path.name}")
    expected_docs = {name: _read(name) for name in ("semantic-assessments.json", "identity-recommendations.json", "identity-decisions.json", "graph-actions.json", "search-plans.json", "retrieval-trace.json", "updated-constraints.json", "research-gap-transitions.json", "validation-results.json", "metrics.json")}
    if manifest.get("projection_hash") != json_hash(expected_docs):
        errors.append("projection_hash_mismatch")

    # HNG2-S protected baselines and canonical layers remain immutable.
    base_manifest = read_json(BASE / "manifest.json", {}) or {}
    for label, expected in (base_manifest.get("protected_artifact_hashes") or {}).items():
        root = ROOT / "data/generated" / label if label != "srm0" else ROOT / "data/generated/srm0"
        if schema_replay.hash_tree(root) != expected:
            errors.append(f"protected_artifact_changed:{label}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"HNG2-SL {args.mode} validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
