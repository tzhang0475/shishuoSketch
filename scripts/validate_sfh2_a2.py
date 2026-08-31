#!/usr/bin/env python3
"""Validate the isolated SFH2.2-A2 independent semantic audit."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a0r.contracts import semantic_diff_paths
from sfh2_a0r_l.common import CHALLENGE_STORIES

from sfh2_a2.common import A1R_L_ROOT, MAX_PROVIDER_ATTEMPTS, MODEL, OUT, PROMPT_VERSIONS, cases_by_cohort, file_hash, read_json, stable_hash, text
from sfh2_a2.contracts import adjudicator_tool, historian_b_tool, validate_deepseek_strict_schema

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "51a07a9d5fb108c13748b7983d64a81181f86be6"


def _record(row: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get("record"), Mapping):
        return row["record"]
    return None


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _contains_keys(value: Any, forbidden: set[str]) -> list[str]:
    return sorted({path for path, child in _walk(value) if isinstance(child, Mapping) for key in child if key in forbidden for path in [f"{path}.{key}"]})


def _load(name: str, default: Any = None, *, replay: str | None = None) -> Any:
    path = OUT / name if replay is None else OUT / "replays" / replay / name
    return read_json(path, default)


def _selector_errors() -> list[str]:
    errors: list[str] = []
    final = _load("final-results.json", {}) or {}
    a_index = {text(row.get("case_id")): row for row in (_load("historian-a-cache-index.json", {}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
    b_rows = {text(row.get("case_id")): row for row in (_load("historian-b-results.json", {}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
    adjudications = {text(row.get("case_id")): row for row in (_load("adjudicator-results.json", {}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
    for row in final.get("records", []) or []:
        if not isinstance(row, Mapping):
            continue
        case_id = text(row.get("case_id"))
        decision = text(row.get("adjudicator_decision"))
        selected = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else None
        if decision == "select_a":
            source = _record(a_index.get(case_id))
            if source is None or selected != source:
                errors.append(f"select_a_copy_drift:{case_id}")
        elif decision == "select_b":
            source = _record(b_rows.get(case_id))
            if source is None or selected != source:
                errors.append(f"select_b_copy_drift:{case_id}")
        adj = adjudications.get(case_id)
        if isinstance(adj, Mapping) and adj.get("valid") is True and text(adj.get("decision")) == "revise":
            declared = set(text(path) for path in adj.get("reviewed_fields", []) or [])
            if set(semantic_diff_paths(_record(a_index.get(case_id)) if text(adj.get("base_record")) == "historian_a" else _record(b_rows.get(case_id)), selected)).difference(declared):
                errors.append(f"undeclared_patch_mutation:{case_id}")
    return errors


def _replay_errors() -> list[str]:
    first = OUT / "replays" / "sfh2-a2-offline-replay-1"
    second = OUT / "replays" / "sfh2-a2-offline-replay-2"
    if not first.is_dir() or not second.is_dir():
        return ["offline_replays_missing"]
    names = sorted({path.name for path in first.iterdir() if path.is_file()} | {path.name for path in second.iterdir() if path.is_file()})
    errors: list[str] = []
    for name in names:
        p = first / name
        q = second / name
        if p.is_file() and q.is_file() and p.read_bytes() != q.read_bytes():
            errors.append(f"replay_not_byte_identical:{name}")
    for directory in (first, second):
        transport = read_json(directory / "transport.json", {}) or {}
        if int(transport.get("new_live_attempts") or 0) != 0:
            errors.append(f"replay_provider_calls:{directory.name}")
    return errors


def validate(*, require_outputs: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    cases = cases_by_cohort()
    if len(cases.get("regression", [])) != 20 or len(cases.get("challenge", [])) != 20:
        errors.append("cohorts_not_20_each")
    if {text(row.get("story_id")) for row in cases.get("challenge", [])} != set(CHALLENGE_STORIES):
        errors.append("challenge_story_set_changed")
    for tool_name, tool in (("historian_b", historian_b_tool()), ("adjudicator", adjudicator_tool())):
        errors.extend(f"{tool_name}:{item}" for item in validate_deepseek_strict_schema(tool["function"]["parameters"]))
    architecture = _load("architecture-freeze.json", {}) or {}
    if require_outputs and not architecture:
        errors.append("architecture_freeze_missing")
    if architecture:
        if architecture.get("baseline_commit") != BASELINE_COMMIT:
            errors.append("baseline_mismatch")
        if architecture.get("model_config", {}).get("historian_b_model") != MODEL:
            errors.append("historian_b_model_changed")
        if architecture.get("model_config", {}).get("temperature") != 0 or architecture.get("model_config", {}).get("thinking") != {"type": "disabled"}:
            errors.append("model_config_changed")
        if architecture.get("model_config", {}).get("prompt_versions") != PROMPT_VERSIONS:
            errors.append("prompt_versions_changed")
        if architecture.get("historian_b_receives_no_historian_a") is not True or architecture.get("historian_b_receives_no_python_flags") is not True:
            errors.append("historian_b_isolation_contract")
    a_cache = _load("historian-a-cache-index.json", {}) or {}
    if require_outputs:
        if a_cache.get("cached_primary_responses") != 40:
            errors.append("historian_a_cache_not_40")
        if a_cache.get("new_historian_a_provider_calls") != 0:
            errors.append("historian_a_new_calls")
    b_results = _load("historian-b-results.json", {}) or {}
    b_rows = b_results.get("records", []) or []
    if require_outputs and len(b_rows) != 40:
        errors.append("historian_b_not_40")
    for artifact_name in ("case-packets.json", "historian-b-results.json", "ab-comparison.json", "adjudicator-results.json", "final-results.json", "challenge-review-bundle.json"):
        if not require_outputs:
            continue
        data = _load(artifact_name, {}) or {}
        leaked = _contains_keys(data, {"expected_canonical_hint", "expected_referent_surface", "must_not_resolve_to", "expected_semantic_kind", "gold"})
        if leaked:
            errors.extend(f"gold_leak:{artifact_name}:{path}" for path in leaked)
    comparison = _load("ab-comparison.json", {}) or {}
    if require_outputs and len(comparison.get("records", []) or []) != 40:
        errors.append("ab_comparison_not_40")
    transport = _load("transport.json", {}) or {}
    if require_outputs:
        if transport.get("model") != MODEL:
            errors.append("transport_model_changed")
        if int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
            errors.append("provider_budget_exceeded")
    metrics = _load("metrics.json", {}) or {}
    if require_outputs and (metrics.get("historian_a_new_calls") != 0 or metrics.get("historian_b_logical_calls") != 40):
        errors.append("call_accounting_contract")
    safety = _load("storage-safety-audit.json", {}) or {}
    if require_outputs:
        for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "substring_candidate_generation", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions", "python_historical_identity_replacements"):
            if safety.get(key) != 0:
                errors.append(f"safety:{key}")
        if safety.get("candidate_only") is not True or safety.get("canonical_write_back") is not False:
            errors.append("storage_contract")
    preservation = _load("semantic-preservation-audit.json", {}) or {}
    if require_outputs and (preservation.get("selector_copy_drift") != 0 or preservation.get("undeclared_patch_mutations") != 0):
        errors.append("selector_or_patch_contract")
    if require_outputs:
        errors.extend(_selector_errors())
        bundle = _load("challenge-review-bundle.json", {}) or {}
        if bundle.get("historical_correctness") != "pending_external_review":
            errors.append("challenge_review_not_pending")
    runtime_files = [ROOT / "scripts/sfh2_a2" / name for name in ("common.py", "contracts.py", "comparison.py", "pipeline.py", "transport.py")]
    for path in runtime_files:
        if not path.is_file():
            errors.append(f"runtime_missing:{path.name}")
            continue
        source = path.read_text(encoding="utf-8")
        if re.search(r"surface\s*==|surface\s+in", source):
            errors.append(f"lexical_surface_rule:{path.name}")
    replay_errors = _replay_errors() if require_outputs else []
    errors.extend(replay_errors)
    return {
        "schema": "sfh2-a2-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "model": MODEL,
        "challenge_stories": list(CHALLENGE_STORIES),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true", help="validate contracts and frozen cohorts without requiring live outputs")
    args = parser.parse_args()
    result = validate(require_outputs=not args.preflight)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
