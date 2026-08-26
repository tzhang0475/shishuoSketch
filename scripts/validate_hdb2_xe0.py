#!/usr/bin/env python3
"""Validate HDB2-XE0 without calling a model.

The validator deliberately treats the existing ``/review/hdb2`` projection
and HDB2-F artifacts as frozen inputs.  It validates only the additive XE0
namespace and the before/after arithmetic.
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

import run_hdb2_xe0 as xe0  # noqa: E402


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _errors_for_run(run_id: str) -> list[str]:
    errors: list[str] = []
    baseline = xe0.freeze_baseline()
    selection = xe0.build_selection()
    if baseline.get("baseline_review_items") != 73:
        errors.append("baseline_review_item_count_not_73")
    production = xe0._production_story_ids()
    story_ids = [str(row.get("story_id")) for row in selection.get("stories", [])]
    if len(story_ids) != len(set(story_ids)):
        errors.append("duplicate_selected_story")
    overlap = sorted(set(story_ids) & production)
    if overlap:
        errors.append(f"selected_story_in_production_scope:{overlap}")
    if not 20 <= len(story_ids) <= 30:
        errors.append(f"story_count_out_of_range:{len(story_ids)}")
    if selection.get("selection_hash") != xe0.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}):
        errors.append("selection_hash_invalid")
    if baseline.get("schema") != xe0.SEMANTIC_BASELINE_SCHEMA:
        errors.append("baseline_schema_not_semantic_v2")
    if baseline.get("semantic_fingerprint") != xe0.semantic_frontier_fingerprint():
        errors.append("semantic_frontier_fingerprint_mismatch")
    if baseline.get("baseline_hash") != xe0.baseline_contract_hash(baseline):
        errors.append("baseline_hash_invalid")
    errors.extend(f"baseline_review_projection:{error}" for error in xe0.validate_review_projection())

    run_dir = xe0.XE0_ROOT / "live" / run_id
    if not run_dir.is_dir():
        return errors + [f"missing_run:{run_id}"]
    manifest = read(run_dir / "manifest.json", {}) or {}
    audit = read(run_dir / "audit.json", {}) or {}
    metrics = read(run_dir / "metrics.json", {}) or {}
    projection = read(run_dir / "review-projection.json", {}) or {}
    if manifest.get("frozen_selection_hash") != selection.get("selection_hash"):
        errors.append("live_selection_hash_mismatch")
    manifest_baseline_hash = manifest.get("baseline_hash")
    legacy_hash = baseline.get("legacy_baseline_hash")
    if manifest_baseline_hash != baseline.get("baseline_hash") and manifest_baseline_hash != legacy_hash:
        errors.append("live_baseline_hash_mismatch")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        errors.append("live_manifest_safety_flags")
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        errors.append("protected_hashes_changed_during_live_run")
    if not xe0.protected_hashes_match_manifest(manifest.get("protected_hashes_after", {})):
        errors.append("protected_hashes_changed_after_live_run")

    baseline_ids = set(baseline.get("review_ids", []))
    resolved_ids = {str(row.get("review_id")) for row in audit.get("resolved_items", [])}
    new_ids = set(str(x) for x in audit.get("new_review_ids", []))
    if not resolved_ids <= baseline_ids:
        errors.append("resolved_nonbaseline_review_id")
    if new_ids & baseline_ids:
        errors.append("new_review_reuses_baseline_review_id")
    if audit.get("baseline_review_items") != 73:
        errors.append("audit_baseline_count_not_73")
    if int(audit.get("old_review_items_resolved") or 0) != len(resolved_ids):
        errors.append("audit_resolved_count_mismatch")
    if int(audit.get("old_review_items_remaining") or 0) != 73 - len(resolved_ids):
        errors.append("audit_remaining_count_mismatch")
    if int(audit.get("new_review_items_created") or 0) != len(new_ids):
        errors.append("audit_new_count_mismatch")
    expected_net = int(audit.get("old_review_items_resolved") or 0) - int(audit.get("new_review_items_created") or 0)
    if int(audit.get("net_review_reduction") or 0) != expected_net:
        errors.append("audit_net_reduction_formula")
    if metrics.get("net_review_reduction") != audit.get("net_review_reduction"):
        errors.append("metrics_audit_net_mismatch")
    if metrics.get("semantic_calls") != metrics.get("person_calls", 0) + metrics.get("temporal_calls", 0):
        errors.append("semantic_call_total_mismatch")
    if projection.get("index", {}).get("item_count") != len(projection.get("items", [])):
        errors.append("review_projection_item_count_mismatch")
    if projection.get("index", {}).get("old_items_remaining") != audit.get("old_review_items_remaining"):
        errors.append("review_projection_remaining_mismatch")
    for item in projection.get("items", []):
        if item.get("candidate_only") is False or item.get("canonical_write_back") is True:
            errors.append(f"unsafe_review_item:{item.get('review_id')}")
    for name in ("person-results.json", "temporal-results.json"):
        document = read(run_dir / name, {}) or {}
        for row in document.get("records", []):
            if row.get("candidate_only") is False or row.get("canonical_write_back") is True:
                errors.append(f"unsafe_result:{name}:{row.get('story_id')}")
            normalization = row.get("normalization") if isinstance(row.get("normalization"), Mapping) else {}
            if normalization.get("canonical_write_back") is True:
                errors.append(f"unsafe_normalization:{name}:{row.get('story_id')}")
    # An old item may be closed only through the explicit compatibility gate,
    # never by normalized surface equality.
    baseline_items = {str(row.get("review_id")): row for row in xe0._frozen_xe0_baseline_items()[1]}
    for resolved in audit.get("resolved_items", []):
        old = baseline_items.get(str(resolved.get("review_id")), {})
        for evidence in resolved.get("evidence", []):
            if not xe0._compatible_old_item(old, evidence):
                errors.append(f"incompatible_old_resolution:{resolved.get('review_id')}")
    if not (ROOT / "site/public/generated/review/hdb2/index.json").is_file():
        errors.append("baseline_review_projection_missing")
    return sorted(set(errors))


def validate(run_id: str) -> dict[str, Any]:
    errors = _errors_for_run(run_id)
    run_dir = xe0.XE0_ROOT / "live" / run_id
    summary = {
        "schema": "hdb2-xe0-validation-summary-v1",
        "run_id": run_id,
        "valid": not errors,
        "errors": errors,
        "candidate_only": True,
        "canonical_write_back": False,
        "baseline_review_items": 73,
        "selection_hash": (read(xe0.SELECTION_PATH, {}) or {}).get("selection_hash"),
        "deterministic_rebuild_checked": False,
    }
    if run_dir.is_dir() and not errors:
        before = {name: (run_dir / name).read_bytes() for name in ("audit.json", "review-projection.json", "metrics.json")}
        xe0.rebuild(run_id)
        after = {name: (run_dir / name).read_bytes() for name in before}
        summary["deterministic_rebuild_checked"] = True
        summary["deterministic_rebuild"] = before == after
        if before != after:
            summary["valid"] = False
            summary["errors"].append("deterministic_rebuild_changed_output")
    out = xe0.XE0_ROOT / "validation-summary.json"
    xe0.write_json(out, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    summary = validate(args.run_id)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
