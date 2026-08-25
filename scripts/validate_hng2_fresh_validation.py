#!/usr/bin/env python3
"""Validate HNG2-V1 holdout artifacts without calling DeepSeek."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/generated/hng2-fresh-validation"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    selection_path = BASE / "selection.json"
    run = BASE / "live" / args.run_id
    failures: list[str] = []
    if not selection_path.is_file():
        failures.append("missing_selection")
    if not run.is_dir():
        failures.append("missing_live_run")
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    selection = load(selection_path)
    manifest = load(run / "manifest.json") if (run / "manifest.json").is_file() else {}
    summary = load(run / "validation-summary.json") if (run / "validation-summary.json").is_file() else {}
    required = ["person-results.json", "temporal-results.json", "review-queue.json", "validation-summary.json", "manifest.json", "preflight.json"]
    failures.extend(f"missing:{name}" for name in required if not (run / name).is_file())
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    if selection.get("story_count") != 24:
        failures.append("selection_story_count")
    if selection.get("overlap_with_previous_hng2"):
        failures.append("selection_overlap")
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        failures.append("selection_hash_mismatch")
    if manifest.get("base_semantic_calls") != 96:
        failures.append("base_semantic_call_count")
    raw_count = len(list((run / "raw-api").glob("*.json")))
    operations = summary.get("operations") or {}
    if operations.get("semantic_calls_attempted", 0) < 96:
        failures.append("semantic_calls_below_base")
    if raw_count == 0:
        failures.append("no_raw_api_responses")
    if manifest.get("canonical_write_back") is not False or summary.get("canonical_write_back") is not False:
        failures.append("canonical_write_back")
    if manifest.get("overlap_with_previous_hng2") != []:
        failures.append("manifest_overlap")
    gates = summary.get("safety_gates") or {}
    for key in (
        "false_identity_promotions_zero",
        "known_reference_wrong_resolution_zero",
        "nonperson_person_id_anomalies_zero",
        "collapsed_nonidentity_self_relations_zero",
        "unsupported_relation_promotions_zero",
        "false_temporal_promotions_zero",
        "scanner_scope_recall_zero",
        "selection_overlap_zero",
        "canonical_write_back_false",
        "contextual_projection_not_direct",
        "exact_provenance_fail_closed",
        "selection_immutable",
    ):
        if gates.get(key) is not True:
            failures.append(f"safety_gate:{key}")
    result = {
        "status": "failed" if failures else "passed",
        "failures": failures,
        "story_count": selection.get("story_count"),
        "semantic_calls_attempted": operations.get("semantic_calls_attempted"),
        "raw_api_files": raw_count,
        "safety_gates_pass": summary.get("safety_gates_pass"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
