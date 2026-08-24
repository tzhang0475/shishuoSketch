#!/usr/bin/env python3
"""Fail-closed validator for HNG2-SC.1 replay/live projections."""

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

import run_hng2_schema_controller_hardening as runner  # noqa: E402


ALLOWED_CLASSIFICATIONS = {
    "valid_card", "card_validation_failure", "response_parse_failure",
    "response_truncated", "provider_request_failure", "provider_rate_limit",
}


def read(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate_replay(root: Path = runner.OUT) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read(root / "manifest.json", {}) or {}
    metrics = read(root / "metrics.json", {}) or {}
    result = read(root / "replay-results.json", {}) or {}
    classifications = read(root / "response-classifications.json", {}) or {}
    rows = classifications.get("rows", []) if isinstance(classifications, Mapping) else []
    fixtures = result.get("fixtures", []) if isinstance(result, Mapping) else []
    _fail(errors, manifest.get("stage") == "hng2-schema-controller-hardening-replay", "wrong_replay_stage")
    _fail(errors, metrics.get("api_calls") == 0, "offline_replay_called_api")
    _fail(errors, metrics.get("canonical_write_back") is False, "canonical_write_back")
    _fail(errors, metrics.get("no_frontier_expansion") is True, "frontier_expansion")
    _fail(errors, set(row.get("classification") for row in rows) <= ALLOWED_CLASSIFICATIONS, "unknown_response_classification")
    expected_hashes = manifest.get("input_hashes", {})
    _fail(errors, expected_hashes.get("hng2_sc_07_raw") == runner.hash_tree(runner.SC_RAW), "sc07_raw_changed")
    _fail(errors, expected_hashes.get("hng2_sl_raw") == runner.hash_tree(runner.SL_RAW), "sl_raw_changed")
    _fail(errors, expected_hashes.get("hng2_schema") == runner.hash_tree(ROOT / "data/generated/hng2-schema"), "schema_input_changed")
    truncated = [row for row in rows if row.get("classification") == "response_truncated"]
    _fail(errors, all(row.get("finish_reason") == "length" for row in truncated), "truncated_not_finish_length")
    _fail(errors, metrics.get("truncated_responses", 0) >= 1, "missing_truncation_regression")
    _fail(errors, metrics.get("reasoning_content_responses_recovered", 0) >= 1, "missing_reasoning_content_recovery")
    _fail(errors, metrics.get("identity_propagation_count", 0) >= 1, "missing_identity_propagation")
    _fail(errors, metrics.get("candidate_upgrade_count", 0) >= 1, "missing_existing_candidate_upgrade")
    _fail(errors, metrics.get("prior_temporal_constraint_preserved") is True, "prior_temporal_constraint_lost")
    fixture_ids = {str(row.get("fixture_id")) for row in fixtures}
    required = {"wu-emperor-propagation", "yu-taiwei-propagation", "yuxi-target-separation", "structural-target", "wangyi-propagation", "prior-temporal-preservation", "known-person-candidate-upgrade", "new-person-transition"}
    _fail(errors, required <= fixture_ids, "required_fixture_missing")
    for row in fixtures:
        if row.get("fixture_id") in required:
            _fail(errors, bool((row.get("validation") or {}).get("valid")), f"fixture_invalid:{row.get('fixture_id')}")
            projection = row.get("projection") or {}
            _fail(errors, projection.get("canonical_write_back", False) is False, f"fixture_canonical_write:{row.get('fixture_id')}")
    by_id = {str(row.get("fixture_id")): row for row in fixtures}
    _fail(errors, (by_id.get("wu-emperor-propagation", {}).get("projection") or {}).get("identity_decision", {}).get("identity_status") == "resolved_existing", "wu_not_resolved_existing")
    _fail(errors, (by_id.get("yuxi-target-separation", {}).get("projection") or {}).get("identity_decision", {}).get("identity_status") == "resolved_new_candidate", "yuxi_target_not_new_candidate")
    _fail(errors, (by_id.get("structural-target", {}).get("projection") or {}).get("identity_decision", {}).get("identity_status") == "not_single_person", "structural_target_not_blocked")
    _fail(errors, (by_id.get("known-person-candidate-upgrade", {}).get("projection") or {}).get("state_delta", {}).get("upgraded_candidates") == ["c0"], "candidate_upgrade_not_projected")
    return {"valid": not errors, "errors": errors, "mode": "replay", "api_calls": 0}


def validate_live(root: Path = runner.OUT) -> dict[str, Any]:
    if not (root / "manifest.json").is_file():
        candidates = [path for path in (root / "live").glob("*") if (path / "manifest.json").is_file()]
        if candidates:
            root = sorted(candidates)[-1]
    errors: list[str] = []
    manifest = read(root / "manifest.json", {}) or {}
    selection = read(root / "selection.json", {}) or {}
    metrics = read(root / "metrics.json", {}) or {}
    _fail(errors, manifest.get("stage") == "hng2-schema-controller-hardening-live", "wrong_live_stage")
    _fail(errors, len(selection.get("cases", [])) == 5, "live_selection_not_five")
    _fail(errors, metrics.get("no_frontier_expansion") is True, "frontier_expansion")
    _fail(errors, metrics.get("preflight_succeeded") is True, "preflight_failed")
    raw_root = ROOT / str(manifest.get("raw_api_root") or "")
    _fail(errors, raw_root.is_dir(), "raw_api_root_missing")
    for path in (root / "search-plans.json",):
        doc = read(path, {}) or {}
        for row in doc.get("plans", []):
            for source in (row.get("plan") or {}).get("preferred_sources", []):
                _fail(errors, source in runner.ALLOWED_SOURCES, f"unapproved_source:{source}")
    return {"valid": not errors, "errors": errors, "mode": "live", "api_calls": metrics.get("api_calls", 0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--run-root", default="")
    args = parser.parse_args()
    root = Path(args.run_root) if args.run_root else runner.OUT
    result = validate_replay(root) if args.mode == "replay" else validate_live(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
