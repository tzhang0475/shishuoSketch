#!/usr/bin/env python3
"""Validate SFH2.2-A1R's strict review transport and cached-primary replay."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a0r.contracts import adjudication_tool, critical_review_tool, semantic_record_tool, validate_deepseek_strict_schema
from sfh2_a0r_l.common import CHALLENGE_STORIES

from sfh2_a1r.common import A1R_LIVE_ROOT, A1R_L_ROOT, MAX_PROVIDER_ATTEMPTS, MODEL, OUT, PROMPT_VERSIONS, STRICT_ENDPOINT, cohort_cases, read_json, stable_hash, text

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "19850ae3db8651809bcc019abde28aecf5c180e3"


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _keys(value: Any) -> set[str]:
    return {path.rsplit(".", 1)[-1].split("[", 1)[0] for path, _ in _walk(value) if path != "$"}


def _selection_errors() -> list[str]:
    errors: list[str] = []
    cases = cohort_cases()
    if len(cases.get("regression", [])) != 20 or len(cases.get("challenge", [])) != 20:
        errors.append("cached_primary_cohorts_not_40")
    for cohort, rows in cases.items():
        if len({(text(row.get("story_id")), text(row.get("mention_id"))) for row in rows}) != len(rows):
            errors.append(f"duplicate_{cohort}_occurrences")
    return errors


def _strict_errors() -> list[str]:
    errors: list[str] = []
    for name, tool in (("primary", semantic_record_tool()), ("reviewer", critical_review_tool()), ("adjudicator", adjudication_tool())):
        errors.extend(f"{name}:{error}" for error in validate_deepseek_strict_schema(tool["function"]["parameters"]))
    return errors


def _artifact_errors() -> list[str]:
    errors: list[str] = []
    required = [
        "root-cause-analysis.json", "strict-schema-probes.json", "primary-cache-revalidation.json",
        "regression-routing.json", "regression-pass2.json", "regression-pass3.json", "regression-final.json", "regression-evaluation.json",
        "challenge-routing.json", "challenge-pass2.json", "challenge-pass3.json", "challenge-final.json", "challenge-human-review.json", "challenge-human-review.md",
        "transport.json", "provider-error-audit.json", "semantic-preservation-audit.json", "storage-safety-audit.json", "validation-summary.json", "recommendation.json",
    ]
    errors.extend(f"missing:{name}" for name in required if not (OUT / name).is_file())
    probe = read_json(OUT / "strict-schema-probes.json", {}) or {}
    if probe.get("all_pass") is not True or probe.get("probe_count") != 3:
        errors.append("strict_schema_probes_not_all_successful")
    if any(row.get("attempts") != 1 for row in probe.get("results", []) if isinstance(row, Mapping)):
        errors.append("probe_retry")
    revalidation = read_json(OUT / "primary-cache-revalidation.json", {}) or {}
    if revalidation.get("cached_primary_responses") != 40 or revalidation.get("new_primary_provider_calls") != 0:
        errors.append("primary_cache_contract")
    # The three dialogue-role records are expected to become valid after the
    # generic role-ontology correction.  A cached response may still expose a
    # separate, pre-existing malformed semantic field; keep that raw witness
    # auditable instead of coercing it into a different historical meaning.
    total_revalidated = int(revalidation.get("after_valid") or 0) + int(revalidation.get("after_invalid") or 0)
    if total_revalidated != 40:
        errors.append("primary_revalidation_count")
    residual = revalidation.get("residual_contract_mismatches")
    if revalidation.get("after_invalid") and not isinstance(residual, list):
        errors.append("primary_residual_mismatch_not_recorded")
    for row in residual or []:
        if not isinstance(row, Mapping) or not row.get("contract_mismatch"):
            errors.append("primary_residual_mismatch_unaudited")
    for name in ("regression-pass2.json", "regression-pass3.json", "challenge-pass2.json", "challenge-pass3.json"):
        document = read_json(OUT / name, {}) or {}
        if {"semantic_record", "revised_semantic_record"}.intersection(_keys(document)):
            errors.append(f"complete_record_in_{name}")
        for row in document.get("records", []) or []:
            if isinstance(row, Mapping) and "patch_ops" not in row and row.get("valid") is True and row.get("decision") == "revise":
                errors.append(f"missing_patch_ops:{name}:{row.get('case_id')}")
    review = read_json(OUT / "challenge-human-review.json", {}) or {}
    if review.get("historical_correctness") != "pending_external_review" or len(review.get("records", []) or []) != 20:
        errors.append("challenge_review_bundle")
    safety = read_json(OUT / "storage-safety-audit.json", {}) or {}
    for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "substring_identity_creation", "related_person_unsafe_promotions", "attribute_person_unsafe_promotions", "collective_person_unsafe_promotions", "python_historical_replacements"):
        if safety.get(key) != 0:
            errors.append(f"safety:{key}")
    if safety.get("candidate_only") is not True or safety.get("canonical_write_back") is not False:
        errors.append("storage_contract")
    preservation = read_json(OUT / "semantic-preservation-audit.json", {}) or {}
    for key in ("selector_copy_drift", "undeclared_patch_mutations"):
        if preservation.get(key) != 0:
            errors.append(f"preservation:{key}")
    transport = read_json(OUT / "transport.json", {}) or {}
    if transport.get("model") != MODEL or int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
        errors.append("transport_model_or_budget")
    if transport.get("http_400_failures") != 0:
        errors.append("review_http_400")
    if transport.get("prompt_versions") != PROMPT_VERSIONS:
        errors.append("transport_prompt_versions")
    return errors


def validate() -> dict[str, Any]:
    errors = _selection_errors() + _strict_errors() + _artifact_errors()
    return {"schema": "sfh2-a1r-validation-v1", "valid": not errors, "errors": sorted(set(errors)), "baseline_commit": BASELINE_COMMIT, "model": MODEL, "endpoint": STRICT_ENDPOINT, "candidate_only": True, "canonical_write_back": False, "challenge_stories": list(CHALLENGE_STORIES)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
