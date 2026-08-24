#!/usr/bin/env python3
"""Validator for HNG2-SC replay/live controller projections."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
from run_hng2_schema_controller import BASE, LIVE_OUT, REPLAY_OUT, hash_tree, load_cases, load_source_map  # noqa: E402


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _errors_for_projection(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = read(root / "manifest.json", {}) or {}
    if manifest.get("canonical_write_back") is not False:
        errors.append("canonical_write_back")
    if manifest.get("no_frontier_expansion") is not True:
        errors.append("frontier_expansion")
    if manifest.get("base_projection_hash") and manifest.get("base_projection_hash") != hash_tree(BASE):
        errors.append("base_projection_changed")
    decisions = read(root / "identity-decisions.json", {}) or {}
    for row in decisions.get("decisions", []):
        if "graph_action" in row or "provisional_person_id" in row:
            errors.append(f"graph_id_in_identity_decision:{row.get('case_id')}")
        if row.get("identity_status") == "resolved_new_candidate" and not row.get("new_entity_key"):
            errors.append(f"new_candidate_without_new_entity_key:{row.get('case_id')}")
    actions = read(root / "graph-actions.json", {}) or {}
    for row in actions.get("actions", []):
        if row.get("action") == "create_provisional_candidate" and not row.get("provisional_person_id"):
            errors.append(f"graph_action_missing_provisional_id:{row.get('case_id')}")
    validation = read(root / "validation-results.json", {}) or {}
    for row in validation.get("results", []):
        if row.get("valid") is False and not row.get("errors"):
            errors.append(f"invalid_without_reason:{row.get('case_id')}:{row.get('round')}")
    return errors


def validate_replay() -> dict[str, Any]:
    root = REPLAY_OUT
    errors = _errors_for_projection(root)
    result = read(root / "replay-results.json", {}) or {}
    metrics = result.get("metrics") or {}
    if metrics.get("api_calls") != 0:
        errors.append("replay_api_calls")
    if metrics.get("response_channels", {}).get("reasoning_content", 0) < 1:
        errors.append("reasoning_content_not_recovered")
    fixtures = result.get("fixtures", [])
    if not fixtures:
        errors.append("missing_offline_fixtures")
    required = {"regression-yu-taiwei", "regression-title-wendi", "regression-structural-kinship", "fixture-wu-emperor"}
    present = {str(row.get("fixture_id")) for row in fixtures}
    errors.extend(f"missing_fixture:{case_id}" for case_id in sorted(required - present))
    if not any(row.get("fixture_id") == "fixture-invalid-new-key-ambiguous" and not row.get("valid") for row in fixtures):
        errors.append("invalid_new_entity_key_not_rejected")
    if not any(row.get("fixture_id") == "hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc" and row.get("valid") and row.get("projection", {}).get("identity_decision", {}).get("identity_status") == "resolved_new_candidate" for row in fixtures):
        errors.append("虞喜_named_person_or_new_candidate_regression")
    return {"stage": "hng2-schema-controller-replay", "valid": not errors, "errors": errors, "metrics": metrics}


def validate_live() -> dict[str, Any]:
    root = LIVE_OUT
    errors = _errors_for_projection(root)
    selection = read(root / "selection.json", {}) or {}
    count = int(selection.get("selected_case_count") or len(selection.get("cases", [])))
    if count < 6 or count > 8:
        errors.append("live_selection_not_6_to_8")
    if selection.get("frozen") is not True or selection.get("no_frontier_expansion") is not True:
        errors.append("live_selection_not_frozen")
    decisions = read(root / "identity-decisions.json", {}) or {}
    actions = read(root / "graph-actions.json", {}) or {}
    if len(decisions.get("decisions", [])) != count:
        errors.append("missing_live_decisions")
    if len(actions.get("actions", [])) != count:
        errors.append("missing_live_graph_actions")
    assessments = read(root / "evidence-cards.json", {}) or {}
    for card in assessments.get("cards", []):
        if card.get("validation", {}).get("valid"):
            payload = card.get("payload") or {}
            if any(key in json.dumps(payload, ensure_ascii=False) for key in ("person_id", "provisional_person_id", "relation_id", "graph_id")):
                errors.append(f"forbidden_id_in_live_card:{card.get('case_id')}:{card.get('round')}")
    return {"stage": "hng2-schema-controller-live", "valid": not errors, "errors": errors, "metrics": read(root / "metrics.json", {}) or {}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    args = parser.parse_args()
    result = validate_replay() if args.mode == "replay" else validate_live()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
