#!/usr/bin/env python3
"""Validate SRM0.4D derived failure-repair projections."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from run_srm0_4b import _read_json  # noqa: E402
from run_srm0_4d import (  # noqa: E402
    ALLOWED_ROOT_CAUSES,
    AUDIT_PATH,
    FIXED_STORIES,
    LIVE_SUMMARY_PATH,
    QUESTION_METRIC_KEYS,
    TERMINAL_STATES,
    _hash,
    _leaf_ids,
    _read,
    _repair_dir,
    _run_dir,
)


def _contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_secret(key) or _contains_secret(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_secret(child) for child in value)
    return "DEEPSEEK_API_KEY" in str(value) or "Bearer " in str(value)


def validate() -> list[str]:
    errors: list[str] = []
    audit = _read(ROOT / AUDIT_PATH)
    if audit.get("canonical_write_back") is not False or audit.get("external_search_performed") is not False:
        errors.append("failure audit has unsafe write/search flags")
    records = audit.get("records") if isinstance(audit.get("records"), list) else []
    for index, row in enumerate(records):
        if not isinstance(row, Mapping):
            errors.append(f"audit record {index} is not an object")
            continue
        if row.get("story_id") not in FIXED_STORIES:
            errors.append(f"audit record {index}: Story outside frozen set")
        if row.get("root_cause") not in ALLOWED_ROOT_CAUSES:
            errors.append(f"audit record {index}: invalid root cause")
        for field in ("model_output_present", "valid_evidence_present", "semantic_delta_present", "rerun_required"):
            if not isinstance(row.get(field), bool):
                errors.append(f"audit record {index}: {field} must be boolean")
        for field in ("current_failure_type", "current_state", "expected_state", "repair_action"):
            if not str(row.get(field) or ""):
                errors.append(f"audit record {index}: empty {field}")
    summary = _read(ROOT / LIVE_SUMMARY_PATH)
    rows = summary.get("stories") if isinstance(summary.get("stories"), list) else []
    by_id = {str(row.get("story_id")): row for row in rows if isinstance(row, Mapping)}
    if set(by_id) != set(FIXED_STORIES):
        errors.append("repaired live summary does not contain exactly six Stories")
    baseline = audit.get("transport_metrics_before") if isinstance(audit.get("transport_metrics_before"), Mapping) else {}
    for story_id in FIXED_STORIES:
        repair = _repair_dir(story_id)
        state_path = repair / "research-state.json"
        manifest = _read(repair / "manifest.json")
        state = _read(state_path)
        if not state_path.is_file() or not manifest:
            errors.append(f"{story_id}: missing repair state/manifest")
            continue
        if state.get("canonical_write_back") is not False or state.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe repair state")
        if manifest.get("canonical_write_back") is not False or manifest.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe repair manifest")
        if _contains_secret(state) or _contains_secret(manifest):
            errors.append(f"{story_id}: secret-like text in repair artifacts")
        questions = {str(q.get("question_id")): q for q in state.get("questions", []) if isinstance(q, Mapping) and q.get("question_id")}
        if len(questions) != len(state.get("questions", [])):
            errors.append(f"{story_id}: duplicate/invalid question IDs")
        leaves = _leaf_ids(questions)
        for qid, question in questions.items():
            parent = question.get("parent_question_id")
            if parent and str(parent) not in questions:
                errors.append(f"{story_id}: orphan child {qid}")
            if parent and not question.get("parent_aspect_id"):
                errors.append(f"{story_id}: child without parent aspect {qid}")
            terminal = question.get("terminal_state")
            if qid in leaves and terminal not in TERMINAL_STATES and terminal != "active":
                errors.append(f"{story_id}: invalid leaf terminal state {qid}: {terminal}")
            if qid not in leaves and terminal is not None and question.get("lineage_status") != "superseded_by_child":
                errors.append(f"{story_id}: parent has a terminal state without lineage marker {qid}")
            for ref in question.get("supporting_refs", []) if isinstance(question.get("supporting_refs"), list) else []:
                if str(ref).startswith(("data/generated/", "data/annotation/")):
                    errors.append(f"{story_id}: generated evidence ref in state {qid}")
                if str(ref) not in set(str(value) for value in state.get("seen_evidence_refs", [])):
                    errors.append(f"{story_id}: supporting ref not in seen refs {qid}: {ref}")
        metrics = state.get("question_metrics")
        if not isinstance(metrics, Mapping):
            errors.append(f"{story_id}: missing question metrics")
        else:
            for key in QUESTION_METRIC_KEYS:
                if not isinstance(metrics.get(key), int) or metrics.get(key, -1) < 0:
                    errors.append(f"{story_id}: invalid question metric {key}")
        row = by_id.get(story_id, {})
        if row.get("question_metrics") != metrics:
            errors.append(f"{story_id}: summary/repaired question metrics mismatch")
        if row.get("transport_metrics") != baseline.get(story_id, {}):
            errors.append(f"{story_id}: transport metrics changed during semantic repair")
        source_state_hash = manifest.get("source_state_sha256")
        source_state_hashes = {
            value for value in (
                _hash(_run_dir(story_id) / "continuation" / "research-state.json"),
                _hash(_run_dir(story_id) / "research-state.json"),
            ) if value
        }
        if source_state_hash and source_state_hash not in source_state_hashes:
            errors.append(f"{story_id}: source state hash mismatch")
        for path, expected in (manifest.get("source_output_hashes") or {}).items() if isinstance(manifest.get("source_output_hashes"), Mapping) else []:
            target = ROOT / str(path)
            if not target.is_file() or sha256_file(ROOT, target) != expected:
                errors.append(f"{story_id}: source output changed: {path}")
        attempts = sorted((repair / "attempts").glob("*.json"))
        actual = [path for path in attempts if _read(path).get("actual_request")]
        if len(actual) > 1:
            errors.append(f"{story_id}: more than one targeted repair request")
        if story_id != "02-yanyu-053" and actual:
            errors.append(f"{story_id}: unexpected model rerun")
        if _contains_secret(row):
            errors.append(f"{story_id}: secret-like text in summary row")
    if _contains_secret(audit):
        errors.append("secret-like text in failure audit")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "portable"), default="full")
    parser.parse_args()
    errors = validate()
    if errors:
        print("SRM0.4D validation failed")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("SRM0.4D validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
