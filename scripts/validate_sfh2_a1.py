#!/usr/bin/env python3
"""Validate the SFH2.2-A1 host-live audit without semantic reinterpretation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
A0R_L = ROOT / "data/generated/sfh2-a0r-l"
OUT = ROOT / "data/generated/sfh2-a1"
SELECTION = ROOT / "data/annotation/sfh2-a0r-l-challenge-selection.json"
EXTERNAL_REVIEW = ROOT / "data/annotation/sfh2-a1-challenge-external-review.json"
BASELINE_COMMIT = "7f9e9431314f54848883390bc990fec1018f2aaa"
SELECTION_HASH = "f3f4a93de3db1f333c3a750555f36f329464707bf8a1fbbcc5a00f7377505e9a"
CHALLENGE_STORIES = [
    "09-pinzao-063",
    "25-paidiao-015",
    "21-qiaoyi-011",
    "10-guizhen-011",
    "02-yanyu-060",
]
GOLD_KEYS = {
    "expected_identity",
    "expected_canonical_hint",
    "expected_role",
    "expected_semantic_kind",
    "expected_referent_surface",
    "must_not_resolve_to",
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _keys(value: Any) -> set[str]:
    return {key for key, _ in _walk(value)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "host-preflight.json",
        "cohort-a-results.json",
        "cohort-a-evaluation.json",
        "cohort-b-results.json",
        "cohort-b-story-consistency.json",
        "challenge-review-priority.json",
        "provider-accounting.json",
        "semantic-preservation-audit.json",
        "storage-safety-audit.json",
        "metrics.json",
        "validation-summary.json",
        "recommendation.json",
        "source-manifest.json",
    )
    for name in required:
        if not (OUT / name).is_file():
            errors.append(f"missing_output:{name}")

    selection = read_json(SELECTION, {}) or {}
    if selection.get("selection_hash") != SELECTION_HASH:
        errors.append("challenge_selection_hash_changed")
    if selection.get("case_count") != 20 or selection.get("story_count") != 5:
        errors.append("challenge_selection_count")
    if selection.get("story_ids") != CHALLENGE_STORIES:
        errors.append("challenge_story_order_or_membership_changed")
    cases = selection.get("cases", []) if isinstance(selection.get("cases"), list) else []
    if len(cases) != 20:
        errors.append("challenge_case_count")
    if any(sum(row.get("story_id") == story for row in cases if isinstance(row, Mapping)) != 4 for story in CHALLENGE_STORIES):
        errors.append("challenge_not_four_per_story")
    if GOLD_KEYS.intersection(_keys(cases)):
        errors.append("gold_in_selection")

    host = read_json(OUT / "host-preflight.json", {}) or {}
    record = host.get("record") if isinstance(host.get("record"), Mapping) else {}
    if host.get("baseline_commit") != BASELINE_COMMIT:
        errors.append("baseline_commit_mismatch")
    if record.get("live_provider_available") is not True or record.get("attempts") != 1:
        errors.append("host_preflight_not_successful_one_shot")
    if record.get("model") != "deepseek-v4-flash" or record.get("temperature") != 0 or record.get("thinking") != {"type": "disabled"}:
        errors.append("host_preflight_model_config_changed")
    if record.get("historical_preflight_sha256") != _sha(A0R_L / "provider-preflight.json"):
        errors.append("historical_preflight_witness_mismatch")

    architecture = read_json(A0R_L / "architecture-freeze.json", {}) or {}
    manifest = read_json(OUT / "source-manifest.json", {}) or {}
    if manifest.get("baseline_commit") != BASELINE_COMMIT:
        errors.append("manifest_baseline_commit_mismatch")
    if manifest.get("architecture_hash") != architecture.get("architecture_hash"):
        errors.append("architecture_reference_mismatch")
    if manifest.get("selection_hash") != SELECTION_HASH:
        errors.append("manifest_selection_hash_mismatch")

    external = read_json(EXTERNAL_REVIEW, {}) or {}
    external_cases = external.get("cases", []) if isinstance(external.get("cases"), list) else []
    if external.get("selection_hash") != SELECTION_HASH or external.get("status") != "pending_external_review":
        errors.append("external_review_contract")
    if len(external_cases) != 20:
        errors.append("external_review_case_count")
    if any(row.get("status") != "pending_external_review" for row in external_cases if isinstance(row, Mapping)):
        errors.append("external_review_not_pending")
    if GOLD_KEYS.intersection(_keys(external)):
        errors.append("gold_in_external_review")

    challenge = read_json(OUT / "cohort-b-results.json", {}) or {}
    challenge_records = challenge.get("records", []) if isinstance(challenge.get("records"), list) else []
    if challenge.get("case_count") != 20 or challenge.get("story_count") != 5 or challenge.get("story_ids") != CHALLENGE_STORIES:
        errors.append("cohort_b_contract")
    if challenge.get("historical_correctness") != "pending_external_review":
        errors.append("challenge_correctness_scored_automatically")
    if GOLD_KEYS.intersection(_keys(challenge)):
        errors.append("gold_in_cohort_b_results")
    if len(challenge_records) != 20:
        errors.append("cohort_b_result_count")

    cohort_a = read_json(OUT / "cohort-a-results.json", {}) or {}
    if cohort_a.get("case_count") != 20 or len(cohort_a.get("records", []) or []) != 20:
        errors.append("cohort_a_result_count")

    metrics = read_json(OUT / "metrics.json", {}) or {}
    safety = read_json(OUT / "storage-safety-audit.json", {}) or {}
    safety_record = safety.get("record") if isinstance(safety.get("record"), Mapping) else {}
    safety_keys = (
        "production_person_creations",
        "canonical_writes",
        "alias_mutations",
        "profile_mutations",
        "substring_candidate_creation",
        "related_person_promotions",
        "attribute_person_promotions",
        "collective_person_promotions",
        "selector_copy_drift",
        "undeclared_patch_mutations",
    )
    for key in safety_keys:
        if int(metrics.get(key) or 0) != 0:
            errors.append(f"unsafe_metric:{key}")
        if int(safety_record.get(key) or 0) != 0:
            errors.append(f"unsafe_safety_record:{key}")
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("metrics_storage_contract")
    if metrics.get("no_full_188_story_live_run") is not True:
        errors.append("full_188_story_live_run")

    accounting = read_json(OUT / "provider-accounting.json", {}) or {}
    if accounting.get("budget_respected") is not True or int(accounting.get("total_authoritative_attempts") or 0) > 80:
        errors.append("provider_budget")
    if int(accounting.get("total_provider_failures") or 0) and int(accounting.get("total_successful_parsed_calls") or 0) < 40:
        errors.append("primary_call_shortfall")

    preservation = read_json(OUT / "semantic-preservation-audit.json", {}) or {}
    preservation_record = preservation.get("record") if isinstance(preservation.get("record"), Mapping) else {}
    if int(preservation_record.get("selection_preservation_failures") or 0) != 0:
        errors.append("selector_copy_drift")

    summary = read_json(OUT / "validation-summary.json", {}) or {}
    if summary.get("candidate_only") is not True or summary.get("canonical_write_back") is not False:
        errors.append("summary_storage_contract")
    if summary.get("challenge_historical_correctness") != "pending_external_review":
        errors.append("summary_external_review_status")

    return {
        "schema": "sfh2-a1-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "selection_hash": SELECTION_HASH,
        "host_preflight_success": record.get("live_provider_available") is True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
