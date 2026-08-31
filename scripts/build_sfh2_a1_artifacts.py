#!/usr/bin/env python3
"""Materialize the SFH2.2-A1 live-validation audit from frozen A0R-L output.

This is a deterministic audit/provenance projection.  It does not interpret
historical language, alter semantic records, or write canonical data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
A0R_L = ROOT / "data/generated/sfh2-a0r-l"
LIVE_RUN = A0R_L / "live/sfh2-a0r-l-host-live-v1"
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def _records(path: Path) -> list[dict[str, Any]]:
    document = read_json(path, {}) or {}
    rows = document.get("records", [])
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _stage_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "records": len(rows),
        "parsed": sum(row.get("classification") == "parsed" for row in rows),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
        "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
        "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in rows),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in rows),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in rows),
        "median_latency_seconds": _median([float(row.get("elapsed_seconds") or 0) for row in rows]),
        "max_latency_seconds": max([float(row.get("elapsed_seconds") or 0) for row in rows] or [0]),
    }


def _median(values: list[float]) -> float:
    values = sorted(value for value in values if value > 0)
    if not values:
        return 0
    middle = len(values) // 2
    result = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
    return round(result, 3)


def _priority_rows(selection: Mapping[str, Any], pass1: list[Mapping[str, Any]], final: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    final_by_case = {str(row.get("case_id")): row for row in final}
    selected_by_case = {str(row.get("case_id")): row for row in selection.get("cases", []) or [] if isinstance(row, Mapping)}
    rows: list[dict[str, Any]] = []
    for row in pass1:
        case_id = str(row.get("case_id"))
        consistency = row.get("consistency") if isinstance(row.get("consistency"), Mapping) else {}
        flags = [flag for flag in consistency.get("flags", []) or [] if isinstance(flag, Mapping)]
        final_row = final_by_case.get(case_id, {})
        reasons: list[str] = []
        if any(str(flag.get("severity")) == "hard" for flag in flags):
            reasons.append("formal_hard_flag")
        if any(str(flag.get("severity")) == "review" for flag in flags):
            reasons.append("formal_review_flag")
        if final_row.get("final_state") == "review_required":
            reasons.append("final_review_required")
        if not row.get("valid"):
            reasons.append("invalid_primary_record")
        if not reasons:
            reasons.append("no_formal_escalation")
        selection_row = selected_by_case.get(case_id, {})
        rows.append({
            "case_id": case_id,
            "story_id": selection_row.get("story_id", row.get("story_id")),
            "mention_id": selection_row.get("mention_id", row.get("mention_id")),
            "surface": selection_row.get("surface", row.get("surface")),
            "formal_flag_types": sorted({str(flag.get("flag_type")) for flag in flags if flag.get("flag_type")}),
            "formal_flag_severities": sorted({str(flag.get("severity")) for flag in flags if flag.get("severity")}),
            "final_state": final_row.get("final_state"),
            "review_priority_reasons": reasons,
            "review_priority": len(reasons) if reasons != ["no_formal_escalation"] else 0,
            "historical_correctness": "not_scored_for_challenge",
        })
    return rows


def _provider_accounting(transport_rows: list[Mapping[str, Any]], preflight: Mapping[str, Any]) -> dict[str, Any]:
    cohorts: dict[str, Any] = {}
    for cohort in ("regression", "challenge"):
        cohort_rows = [row for row in transport_rows if str(row.get("unit_id", "")).startswith(cohort + ":")]
        by_stage = {
            stage: _stage_summary([row for row in cohort_rows if row.get("stage") == stage])
            for stage in ("primary_historian", "critical_reviewer", "adjudicator")
        }
        cohorts[cohort] = {
            "logical_requests": len({(row.get("stage"), row.get("unit_id")) for row in cohort_rows}),
            "attempts": len(cohort_rows),
            "successful_parsed_calls": sum(row.get("classification") == "parsed" for row in cohort_rows),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in cohort_rows),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in cohort_rows),
            "by_stage": by_stage,
        }
    return {
        "schema": "sfh2-a1-provider-accounting-v1",
        "model": preflight.get("model"),
        "temperature": preflight.get("temperature"),
        "thinking": preflight.get("thinking"),
        "connectivity_probe": {
            "attempts": preflight.get("attempts"),
            "successful": preflight.get("live_provider_available") is True,
            "prompt_tokens": int((preflight.get("usage") or {}).get("prompt_tokens") or 0),
            "completion_tokens": int((preflight.get("usage") or {}).get("completion_tokens") or 0),
            "total_tokens": int((preflight.get("usage") or {}).get("total_tokens") or 0),
            "latency_seconds": preflight.get("elapsed_seconds"),
        },
        "cohorts": cohorts,
        "total_authoritative_attempts": len(transport_rows),
        "total_successful_parsed_calls": sum(row.get("classification") == "parsed" for row in transport_rows),
        "total_provider_failures": sum(row.get("classification") == "provider_request_failure" for row in transport_rows),
        "total_retries": sum(int(row.get("attempt") or 1) > 1 for row in transport_rows),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in transport_rows),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in transport_rows),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in transport_rows),
        "median_latency_seconds": _median([float(row.get("elapsed_seconds") or 0) for row in transport_rows]),
        "max_latency_seconds": max([float(row.get("elapsed_seconds") or 0) for row in transport_rows] or [0]),
        "budget": 80,
        "budget_respected": len(transport_rows) <= 80,
        "no_additional_retry_after_run": True,
    }


def main() -> int:
    selection = read_json(SELECTION, {}) or {}
    preflight = read_json(A0R_L / "host-live/provider-preflight.json", {}) or {}
    metrics = read_json(A0R_L / "metrics.json", {}) or {}
    transport_rows = read_json(LIVE_RUN / "transport.json", []) or []
    if not isinstance(transport_rows, list):
        raise RuntimeError("live_transport_not_array")
    if selection.get("selection_hash") != SELECTION_HASH:
        raise RuntimeError("challenge_selection_hash_changed")
    if preflight.get("live_provider_available") is not True:
        raise RuntimeError("host_preflight_not_successful")
    OUT.mkdir(parents=True, exist_ok=True)

    source_files = {
        name: reference(A0R_L / name)
        for name in (
            "architecture-freeze.json",
            "challenge-selection.json",
            "challenge-selection-hash.json",
            "case-packets.json",
            "regression-pass1.json",
            "regression-pass2.json",
            "regression-pass3.json",
            "regression-final.json",
            "regression-evaluation.json",
            "challenge-pass1.json",
            "challenge-pass2.json",
            "challenge-pass3.json",
            "challenge-final.json",
            "challenge-human-review.json",
            "challenge-human-review.md",
            "challenge-story-consistency.json",
            "semantic-preservation-audit.json",
            "storage-safety-audit.json",
            "metrics.json",
            "transport.json",
        )
    }
    source_files["host-live/provider-preflight.json"] = reference(A0R_L / "host-live/provider-preflight.json")
    source_files["live/sfh2-a0r-l-host-live-v1/transport.json"] = reference(LIVE_RUN / "transport.json")

    regression_final = _records(A0R_L / "regression-final.json")
    challenge_final = _records(A0R_L / "challenge-final.json")
    regression_pass1 = _records(A0R_L / "regression-pass1.json")
    challenge_pass1 = _records(A0R_L / "challenge-pass1.json")
    challenge_story_consistency = read_json(A0R_L / "challenge-story-consistency.json", {}) or {}

    freeze = read_json(A0R_L / "architecture-freeze.json", {}) or {}
    write_json(OUT / "host-preflight.json", {
        "schema": "sfh2-a1-host-preflight-v1",
        "baseline_commit": BASELINE_COMMIT,
        "source": source_files["host-live/provider-preflight.json"],
        "record": preflight,
        "historical_failed_preflight_preserved": preflight.get("historical_preflight_sha256"),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "cohort-a-results.json", {
        "schema": "sfh2-a1-cohort-a-results-v1",
        "cohort": "regression",
        "case_count": 20,
        "records": regression_final,
        "pass1_records": regression_pass1,
        "stage_artifacts": {key: source_files[key] for key in source_files if key.startswith("regression-")},
        "evaluation_artifact": source_files["regression-evaluation.json"],
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "cohort-a-evaluation.json", {
        "schema": "sfh2-a1-cohort-a-evaluation-v1",
        "source": source_files["regression-evaluation.json"],
        "evaluation": read_json(A0R_L / "regression-evaluation.json", {}) or {},
        "review_stage_provider_failures": metrics.get("regression", {}).get("pass2_provider_failures", 0),
        "historical_identity_accuracy_is_evaluated": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "cohort-b-results.json", {
        "schema": "sfh2-a1-cohort-b-results-v1",
        "cohort": "challenge",
        "case_count": 20,
        "story_count": 5,
        "story_ids": CHALLENGE_STORIES,
        "records": challenge_final,
        "pass1_records": challenge_pass1,
        "story_consistency": challenge_story_consistency,
        "stage_artifacts": {key: source_files[key] for key in source_files if key.startswith("challenge-")},
        "historical_correctness": "pending_external_review",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "cohort-b-story-consistency.json", {
        "schema": "sfh2-a1-cohort-b-story-consistency-v1",
        "source": source_files["challenge-story-consistency.json"],
        "record": challenge_story_consistency,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "challenge-review-priority.json", {
        "schema": "sfh2-a1-challenge-review-priority-v1",
        "historical_correctness": "pending_external_review",
        "records": _priority_rows(selection, challenge_pass1, challenge_final),
        "priority_is_review_routing_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "provider-accounting.json", _provider_accounting(transport_rows, preflight))
    write_json(OUT / "semantic-preservation-audit.json", {
        "schema": "sfh2-a1-semantic-preservation-audit-v1",
        "source": source_files["semantic-preservation-audit.json"],
        "record": read_json(A0R_L / "semantic-preservation-audit.json", {}) or {},
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "storage-safety-audit.json", {
        "schema": "sfh2-a1-storage-safety-audit-v1",
        "source": source_files["storage-safety-audit.json"],
        "record": read_json(A0R_L / "storage-safety-audit.json", {}) or {},
        "candidate_only": True,
        "canonical_write_back": False,
    })

    external_rows = [
        {
            "case_id": row.get("case_id"),
            "story_id": row.get("story_id"),
            "mention_id": row.get("mention_id"),
            "surface": row.get("surface"),
            "status": "pending_external_review",
        }
        for row in selection.get("cases", []) or []
        if isinstance(row, Mapping)
    ]
    write_json(EXTERNAL_REVIEW, {
        "schema": "sfh2-a1-challenge-external-review-v1",
        "pilot": "SFH2.2-A1",
        "selection_hash": SELECTION_HASH,
        "status": "pending_external_review",
        "cases": external_rows,
        "gold_not_fabricated": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    accounting = read_json(OUT / "provider-accounting.json", {}) or {}
    safety = read_json(A0R_L / "storage-safety-audit.json", {}) or {}
    a1_metrics = {
        "schema": "sfh2-a1-metrics-v1",
        "pilot": "SFH2.2-A1",
        "baseline_commit": BASELINE_COMMIT,
        "host_preflight_success": True,
        "regression_cases": 20,
        "challenge_stories": 5,
        "challenge_mentions": 20,
        "challenge_selection_hash": SELECTION_HASH,
        "regression_summary": metrics.get("regression", {}),
        "challenge_summary": metrics.get("challenge", {}),
        "provider_accounting": accounting,
        "selector_copy_drift": metrics.get("selector_copy_drift", 0),
        "undeclared_patch_mutations": metrics.get("undeclared_patch_mutations", 0),
        "production_person_creations": safety.get("production_person_creations", 0),
        "canonical_writes": safety.get("canonical_writes", 0),
        "alias_mutations": safety.get("alias_mutations", 0),
        "profile_mutations": safety.get("profile_mutations", 0),
        "substring_candidate_creation": safety.get("substring_candidate_creation", 0),
        "related_person_promotions": safety.get("related_person_promotions", 0),
        "attribute_person_promotions": safety.get("attribute_person_promotions", 0),
        "collective_person_promotions": safety.get("collective_person_promotions", 0),
        "external_challenge_review": "pending_external_review",
        "no_full_188_story_live_run": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(OUT / "metrics.json", a1_metrics)
    validation = {
        "schema": "sfh2-a1-validation-summary-v1",
        "baseline_commit": BASELINE_COMMIT,
        "architecture_hash": freeze.get("architecture_hash"),
        "selection_hash": SELECTION_HASH,
        "host_preflight_success": True,
        "challenge_historical_correctness": "pending_external_review",
        "review_provider_failures": accounting.get("total_provider_failures", 0),
        "selector_copy_drift": a1_metrics["selector_copy_drift"],
        "undeclared_patch_mutations": a1_metrics["undeclared_patch_mutations"],
        "candidate_only": True,
        "canonical_write_back": False,
        "external_review_artifact": str(EXTERNAL_REVIEW.relative_to(ROOT)),
    }
    write_json(OUT / "validation-summary.json", validation)
    write_json(OUT / "recommendation.json", {
        "schema": "sfh2-a1-recommendation-v1",
        "recommendation": "sfh2_external_review_required",
        "reason": "Cohort A did not meet the live identity threshold and routed review calls failed at the provider; challenge correctness remains pending external review.",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "source-manifest.json", {
        "schema": "sfh2-a1-source-manifest-v1",
        "baseline_commit": BASELINE_COMMIT,
        "architecture_hash": freeze.get("architecture_hash"),
        "selection_hash": SELECTION_HASH,
        "source_files": source_files,
        "live_run": "data/generated/sfh2-a0r-l/live/sfh2-a0r-l-host-live-v1",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    print(json.dumps({"output": str(OUT.relative_to(ROOT)), "challenge_external_review": str(EXTERNAL_REVIEW.relative_to(ROOT)), "recommendation": "sfh2_external_review_required"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
