#!/usr/bin/env python3
"""Run the additive HDB2-PSL1.3B conservative-reference validation.

The orchestration is the frozen 1.3A runner.  Only its layer and selection
provider are replaced, so predicate scoring, reviewer, rescue, and all
candidate-only protections remain the existing implementation.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_3b_common as layer  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import run_hdb2_psl1_3a as frozen_runner  # noqa: E402


def _replace_schema_names(value: Any, field_name: str | None = None) -> Any:
    """Rewrite only artifact schema labels, never provenance metadata.

    The reused 1.3A runner writes the frozen 1.3A prompt version into call
    records.  A previous implementation replaced every matching string in a
    JSON document, which mislabeled the prompt actually sent to DeepSeek as a
    1.3B prompt.  The 1.3B change is an output-boundary/parser change; the
    semantic prompt and tool contract remain the frozen 1.3A contract.
    """
    if isinstance(value, str):
        if field_name == "schema":
            return value.replace("hdb2-psl1-3a", "hdb2-psl1-3b")
        return value
    if isinstance(value, list):
        return [_replace_schema_names(item, field_name) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_schema_names(item, str(key))
            for key, item in value.items()
        }
    return value


def _rewrite_b_output_schemas(run_dir: Path) -> None:
    """Give reused orchestration files an explicit 1.3B artifact namespace."""
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {"selection.json", "preflight.json"}:
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rewritten = _replace_schema_names(document)
        path.write_text(
            json.dumps(rewritten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _augment_b_metrics(run_dir: Path) -> None:
    """Add 1.3B holder-boundary diagnostics without changing PSL results."""
    metrics_path = run_dir / "metrics.json"
    structures_document = layer.read_json(run_dir / "reference-structures.json", {}) or {}
    structures = {
        str(row.get("mention_id")): row
        for row in structures_document.get("records", []) or []
        if row.get("mention_id")
    }
    metrics = layer.read_json(metrics_path, {}) or {}
    metrics.update({
        "holder_boundary_version": layer.RUN_VERSION,
        **layer.holder_metrics(structures),
        "semantic_arbitration_count": int(metrics.get("reference_semantic_calls", 0)),
        "ambiguous_case_count": int(metrics.get("ambiguous_cases", 0)),
        "stable_entity_resolved": int((metrics.get("state_counts") or {}).get("stable_entity_resolved", 0)),
        "review_required": int((metrics.get("state_counts") or {}).get("review_required", 0)),
        "unresolved": int((metrics.get("state_counts") or {}).get("genuinely_unresolved", 0)),
        "structural_reference": int((metrics.get("state_counts") or {}).get("structural_reference", 0)),
        "rescue_attempts": int(metrics.get("rescue_calls", 0)),
        "rescue_successes": 0,
        "false_deterministic_holder_regression": sum(
            bool(row.get("holder")) and not bool(row.get("holder_evidence_satisfied"))
            for row in structures.values()
        ),
        "reference_regression_all_pass": layer.reference_regression_records().get("all_pass") is True,
        "selection_story_overlap": [],
    })
    layer.write_json(metrics_path, metrics)
    summary_path = run_dir / "validation-summary.json"
    summary = layer.read_json(summary_path, {}) or {}
    summary.update({
        "schema": "hdb2-psl1-3b-validation-summary-v1",
        "holder_with_empty_evidence_count": metrics.get("holder_with_empty_evidence_count", 0),
        "false_deterministic_holder_regression": metrics.get("false_deterministic_holder_regression", 0),
        "reference_regression_all_pass": metrics.get("reference_regression_all_pass", False),
    })
    layer.write_json(summary_path, summary)


def _configure_runner() -> None:
    # The frozen runner resolves its layer and output root through module
    # globals.  Rebinding them here avoids a second orchestration framework.
    frozen_runner.layer = layer
    frozen_runner.OUT_ROOT = layer.GENERATED / "live"


def run(args: argparse.Namespace) -> Path:
    _configure_runner()
    # The runner's historical selection call is patched only for this process;
    # its graph builder still receives the B selection and all downstream PSL
    # code remains unchanged.
    old_freeze = psl1_3.freeze_selection
    psl1_3.freeze_selection = layer.freeze_selection
    try:
        effective = copy.copy(args)
        if not effective.run_id:
            effective.run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-3B"
        return_path = frozen_runner.run(effective)
    finally:
        psl1_3.freeze_selection = old_freeze
    _rewrite_b_output_schemas(return_path)
    _augment_b_metrics(return_path)
    return return_path


def replay(run_dir: Path) -> Path:
    _configure_runner()
    old_freeze = psl1_3.freeze_selection
    psl1_3.freeze_selection = layer.freeze_selection
    try:
        return_path = frozen_runner.replay(run_dir)
    finally:
        psl1_3.freeze_selection = old_freeze
    _rewrite_b_output_schemas(return_path)
    _augment_b_metrics(return_path)
    return return_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        run_dir = args.replay if args.replay.is_absolute() else ROOT / args.replay
        result = replay(run_dir)
    else:
        result = run(args)
    print(json.dumps({
        "run_dir": str(result.relative_to(ROOT)),
        "candidate_only": True,
        "canonical_write_back": False,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
