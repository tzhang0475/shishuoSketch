#!/usr/bin/env python3
"""Validate the isolated SFH2.2-A2R adjudicator-contract replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0r.contracts import semantic_diff_paths

from sfh2_a2.common import cases_by_cohort
from sfh2_a2r.common import A2_ROOT, MAX_PROVIDER_ATTEMPTS, OUT, ROOT, a2_artifact_hashes, a2_raw_hashes, architecture_freeze, read_json, text
from sfh2_a2r.contracts import adjudicator_tool, validate_deepseek_strict_schema

BASELINE_COMMIT = "32e5081d57766f43456becfcb340206acae1f950"


def _load(name: str, *, replay: str | None = None, default: Any = None) -> Any:
    path = OUT / name if replay is None else OUT / "replays" / replay / name
    return read_json(path, default)


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row[key]
    return None


def _walk(value: Any, path: str = "$"):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _forbidden_keys(value: Any, keys: set[str]) -> list[str]:
    return sorted(path for path, child in _walk(value) if isinstance(child, Mapping) for key in child if key in keys for path in [f"{path}.{key}"])


def _replay_errors() -> list[str]:
    first = OUT / "replays" / "sfh2-a2r-offline-replay-1"
    second = OUT / "replays" / "sfh2-a2r-offline-replay-2"
    if not first.is_dir() or not second.is_dir():
        return ["offline_replays_missing"]
    names = sorted({p.name for p in first.iterdir() if p.is_file()} | {p.name for p in second.iterdir() if p.is_file()})
    errors: list[str] = []
    # Raw/transport paths are operational; all semantic and audit artifacts
    # must be byte-identical.  The pipeline keeps replay raw witnesses out of
    # those deterministic root files.
    operational = {"transport.json", "architecture-freeze.json"}
    for name in names:
        if name in operational:
            continue
        left, right = first / name, second / name
        if left.is_file() and right.is_file() and left.read_bytes() != right.read_bytes():
            errors.append(f"replay_not_byte_identical:{name}")
    for directory in (first, second):
        transport = read_json(directory / "transport.json", {}) or {}
        if int(transport.get("new_live_attempts") or 0) != 0:
            errors.append(f"replay_provider_calls:{directory.name}")
    return errors


def validate(*, require_outputs: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    tool = adjudicator_tool()
    errors.extend(validate_deepseek_strict_schema(tool["function"]["parameters"]))
    if "base_record" in json.dumps(tool, ensure_ascii=False):
        errors.append("base_record_present_in_live_contract")
    cases = cases_by_cohort()
    if len(cases.get("regression", [])) != 20 or len(cases.get("challenge", [])) != 20:
        errors.append("frozen_cohorts_changed")
    freeze = _load("architecture-freeze.json", default={}) or {}
    if require_outputs and not freeze:
        errors.append("architecture_freeze_missing")
    if freeze:
        if freeze.get("baseline_commit") != BASELINE_COMMIT:
            errors.append("baseline_mismatch")
        if freeze.get("model_config", {}).get("max_provider_attempts") != MAX_PROVIDER_ATTEMPTS:
            errors.append("provider_budget_freeze_mismatch")
        if freeze.get("candidate_only") is not True or freeze.get("canonical_write_back") is not False:
            errors.append("storage_freeze_mismatch")
        if freeze.get("a2_artifact_hashes") != a2_artifact_hashes():
            errors.append("immutable_a2_artifact_changed")
        if freeze.get("a2_raw_hashes") != a2_raw_hashes():
            errors.append("immutable_a2_raw_witness_changed")
    if require_outputs:
        required = (
            "historian-a-cache-index.json", "historian-b-cache-reuse.json", "historian-b-recovery.json",
            "ab-comparison.json", "disagreement-hierarchy.json", "adjudicator-results.json", "final-results.json",
            "regression-evaluation.json", "selection-matrix.json", "a-error-recovery.json", "b-error-protection.json",
            "common-mode-error-audit.json", "adjudicator-damage-audit.json", "challenge-final.json",
            "challenge-review-bundle.json", "challenge-review-bundle.md", "policy-simulation.json", "transport.json",
            "semantic-preservation-audit.json", "storage-safety-audit.json", "validation-summary.json", "recommendation.json",
            "adjudicator-schema-probe.json", "adjudicator-contract-v2.json",
        )
        errors.extend(f"missing_output:{name}" for name in required if not (OUT / name).is_file())
        a_cache = _load("historian-a-cache-index.json", default={}) or {}
        if a_cache.get("cached_primary_responses") != 40 or a_cache.get("new_historian_a_provider_calls") != 0:
            errors.append("historian_a_cache_contract")
        b_reuse = _load("historian-b-cache-reuse.json", default={}) or {}
        if int(b_reuse.get("valid_reused") or 0) != 36:
            errors.append("valid_historian_b_cache_not_reused")
        recovery = _load("historian-b-recovery.json", default={}) or {}
        recovery_rows = recovery.get("records", []) or []
        if len(recovery_rows) > 4:
            errors.append("too_many_b_recovery_cases")
        if any(row.get("original_raw_response_preserved") is not True or row.get("historian_b_recovery_attempt") is not True for row in recovery_rows if isinstance(row, Mapping)):
            errors.append("b_recovery_provenance_missing")
        transport = _load("transport.json", default={}) or {}
        if int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
            errors.append("provider_budget_exceeded")
        probe = _load("adjudicator-schema-probe.json", default={}) or {}
        if probe.get("strict_schema_errors"):
            errors.append("schema_probe_contract_invalid")
        if transport.get("http_400_failures"):
            errors.append("provider_http_400")
        comparisons = _load("ab-comparison.json", default={}) or {}
        comparison_rows = {text(row.get("case_id")): row for row in comparisons.get("records", []) or [] if isinstance(row, Mapping)}
        adjudications = _load("adjudicator-results.json", default={}) or {}
        adj_rows = {text(row.get("case_id")): row for row in adjudications.get("records", []) or [] if isinstance(row, Mapping)}
        required_adj = {case_id for case_id, row in comparison_rows.items() if row.get("substantive_disagreement") is True}
        if set(adj_rows) != required_adj:
            errors.append("not_all_substantive_disagreements_adjudicated")
        if any(row.get("valid") is not True for row in adj_rows.values()):
            errors.append("adjudicator_contract_invalid")
        final_doc = _load("final-results.json", default={}) or {}
        a_rows = {text(row.get("case_id")): row for row in (_load("historian-a-cache-index.json", default={}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
        b_rows = {text(row.get("case_id")): row for row in (_load("historian-b-cache-reuse.json", default={}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
        for final in final_doc.get("records", []) or []:
            if not isinstance(final, Mapping):
                continue
            case_id = text(final.get("case_id"))
            decision = text(final.get("adjudicator_decision"))
            selected = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
            if decision == "select_a" and selected != _record(a_rows.get(case_id)):
                errors.append(f"select_a_copy_drift:{case_id}")
            if decision == "select_b" and selected != _record(b_rows.get(case_id)):
                errors.append(f"select_b_copy_drift:{case_id}")
            adj = adj_rows.get(case_id, {})
            if text(adj.get("decision")) in {"revise_a", "revise_b"}:
                base = _record(a_rows.get(case_id)) if text(adj.get("decision")) == "revise_a" else _record(b_rows.get(case_id))
                changed = set(semantic_diff_paths(base, selected))
                declared = {text(op.get("path")) for op in adj.get("patch_ops", []) or [] if isinstance(op, Mapping)}
                if not changed.issubset(declared):
                    errors.append(f"undeclared_patch_mutation:{case_id}")
        preservation = _load("semantic-preservation-audit.json", default={}) or {}
        if preservation.get("selector_copy_drift") != 0 or preservation.get("undeclared_patch_mutations") != 0:
            errors.append("semantic_preservation_failure")
        safety = _load("storage-safety-audit.json", default={}) or {}
        for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "substring_candidate_generation", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions", "python_historical_identity_replacements"):
            if int(safety.get(key) or 0) != 0:
                errors.append(f"safety:{key}")
        if safety.get("candidate_only") is not True or safety.get("canonical_write_back") is not False:
            errors.append("storage_contract")
        # No live provider-facing or materialized A2R record may carry the
        # removed field.  A2's historical artifact is intentionally excluded.
        for name in ("adjudicator-results.json", "final-results.json", "ab-comparison.json", "historian-b-recovery.json"):
            leaked = _forbidden_keys(_load(name, default={}), {"base_record"})
            if leaked:
                errors.extend(f"base_record_leak:{name}:{path}" for path in leaked)
        bundle = _load("challenge-review-bundle.json", default={}) or {}
        if bundle.get("historical_correctness") != "pending_external_review":
            errors.append("challenge_gold_status_changed")
        errors.extend(_replay_errors())
    return {
        "schema": "sfh2-a2r-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    result = validate(require_outputs=not args.preflight)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
