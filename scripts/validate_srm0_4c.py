#!/usr/bin/env python3
"""Validate SRM0.4C continuation isolation and transport accounting."""

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
from run_srm0_4c import ELIGIBLE_STORIES, _run_dir, _question_metrics, _read  # noqa: E402
from srm0_4b_common import FIXED_STORIES, LIVE_SUMMARY_PATH, TRANSPORT_FAILURE_CLASSES  # noqa: E402


QUESTION_KEYS = (
    "evaluable_question_count", "valid_question_count", "reading_sufficient_question_count",
    "conflicted_question_count", "unresolved_question_count", "semantic_failed_question_count",
)


def validate() -> list[str]:
    errors: list[str] = []
    summary = _read(ROOT / LIVE_SUMMARY_PATH)
    rows = summary.get("stories") if isinstance(summary.get("stories"), list) else []
    by_id = {str(row.get("story_id")): row for row in rows if isinstance(row, Mapping)}
    if set(by_id) != set(FIXED_STORIES):
        errors.append("live summary does not contain exactly the frozen six Stories")
    aggregate = summary.get("aggregate", {}) if isinstance(summary.get("aggregate"), Mapping) else {}
    for key in QUESTION_KEYS:
        if not isinstance(aggregate.get(key), int) or aggregate.get(key, -1) < 0:
            errors.append(f"missing question-level metric: {key}")
    for story_id in ELIGIBLE_STORIES:
        run_dir = _run_dir(story_id)
        cdir = run_dir / "continuation"
        if not cdir.is_dir():
            errors.append(f"{story_id}: missing continuation directory")
            continue
        manifest = _read(cdir / "manifest.json")
        if manifest.get("canonical_write_back") is not False or manifest.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe continuation manifest")
        hashes = manifest.get("source_artifact_hashes", {})
        if not isinstance(hashes, Mapping):
            errors.append(f"{story_id}: missing preserved source hashes")
        else:
            for name, expected in hashes.items():
                target = run_dir / str(name)
                if not target.is_file() or sha256_file(ROOT, target) != expected:
                    errors.append(f"{story_id}: preserved source artifact changed: {name}")
        attempts = sorted((cdir / "attempts").glob("round-*-attempt-*.json"))
        rounds: dict[str, list[int]] = {}
        for path in attempts:
            row = _read(path)
            if "DEEPSEEK_API_KEY" in path.read_text(encoding="utf-8", errors="ignore"):
                errors.append(f"{story_id}: secret-like key in attempt artifact")
            key = f"round-{int(row.get('round', -1)):02d}"
            rounds.setdefault(key, []).append(int(row.get("attempt", 0)))
            if int(row.get("attempt", 0)) not in {1, 2}:
                errors.append(f"{story_id}: attempt outside one-retry bound: {path.name}")
        for key, values in rounds.items():
            if len(values) > 2 or sorted(values) != list(range(min(values), max(values) + 1)):
                errors.append(f"{story_id}: non-contiguous attempts in {key}")
        cstate = _read(cdir / "research-state.json")
        if cstate.get("canonical_write_back") is not False or cstate.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe continuation state")
        row = by_id.get(story_id, {})
        tm = row.get("transport_metrics", {}) if isinstance(row.get("transport_metrics"), Mapping) else {}
        if int(tm.get("transport_retry_count", 0)) > sum(max(0, len(values) - 1) for values in rounds.values()):
            errors.append(f"{story_id}: retry metric exceeds attempt logs")
        # SRM0.4D may replace only the derived question projection.  The C
        # continuation and its raw responses remain the authority for
        # transport validation, while D's explicit metrics are authoritative
        # for the repaired summary row.
        repair_state = _read(run_dir / "repair" / "research-state.json")
        if isinstance(repair_state.get("question_metrics"), Mapping):
            expected_q = dict(repair_state["question_metrics"])
        else:
            expected_q = _question_metrics(
                {str(q.get("question_id")): q for q in cstate.get("questions", []) if isinstance(q, Mapping) and q.get("question_id")},
                cstate.get("semantic_failed_questions", []) if isinstance(cstate.get("semantic_failed_questions"), list) else [],
                cstate.get("protocol_errors", []) if isinstance(cstate.get("protocol_errors"), list) else [],
                cstate.get("transport_errors", []) if isinstance(cstate.get("transport_errors"), list) else [],
            )
        if row.get("question_metrics") != expected_q:
            errors.append(f"{story_id}: question metrics do not match continuation state")
    for story_id in ("25-paidiao-007", "02-yanyu-053"):
        if not (ROOT / "data/generated/srm0" / story_id / "convergence" / "live").is_dir():
            errors.append(f"preserved Story missing live directory: {story_id}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "portable"), default="full")
    parser.parse_args()
    errors = validate()
    if errors:
        print("SRM0.4C validation failed")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("SRM0.4C validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
