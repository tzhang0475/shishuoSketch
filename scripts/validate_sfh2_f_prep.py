#!/usr/bin/env python3
"""Validate the offline SFH2.2-F-prep production preflight.

This validator is deliberately read-only.  It validates the compact planning
artifacts, exact occurrence integrity, frozen architecture witnesses, and
prospective C3 growth policy; it has no provider or canonical-write path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping

from audit_repository_growth import audit_repository
from sfh2_f_prep.common import (
    BASELINE_COMMIT,
    FROZEN_OUT,
    OUT,
    ROOT,
    SC1_CURRENT,
    SC1_FROZEN,
    build_occurrence_inventory,
    file_hash,
    load_authority,
    protected_hashes,
    read_json,
    tree_digest,
)


EXPECTED_FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
EXPECTED_CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
EXPECTED_IDENTITY_MANIFEST_SHA256 = "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e"
EXPECTED_GOLD_SHA256 = "177ab3018e6741c3deaf3b5f957bc177df8c4f416ee9a9035bdf6027f7d7e3a7"

OUTPUT_FILES = (
    "production-scope.json",
    "occurrence-manifest.json",
    "exact-occurrence-audit.json",
    "identity-readiness.json",
    "production-dag.json",
    "production-schema.json",
    "review-routing-policy.json",
    "cache-reuse-plan.json",
    "checkpoint-policy.json",
    "provider-failure-policy.json",
    "call-budget.json",
    "token-storage-estimate.json",
    "artifact-lifecycle-plan.json",
    "f1-selection.json",
    "f1-stop-conditions.json",
    "f1-success-gate.json",
    "preflight-validation.json",
    "metrics.json",
    "recommendation.json",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    ).stdout.strip()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _status_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    lines = completed.stdout.splitlines()
    paths: list[str] = []
    for line in lines:
        if not line:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw)
    return paths


def _validate_candidate_flags(value: Any, label: str) -> None:
    for path, child in _walk(value):
        if not isinstance(child, Mapping):
            continue
        if "canonical_write_back" in child:
            _assert(child.get("canonical_write_back") is False, f"canonical write flag at {label}{path}")
        if "candidate_only" in child:
            _assert(child.get("candidate_only") is True, f"candidate flag at {label}{path}")


def _validate_exact_occurrences() -> dict[str, Any]:
    authority = load_authority()
    records, recomputed = build_occurrence_inventory(authority)
    document = read_json(OUT / "exact-occurrence-audit.json", {}) or {}
    manifest = read_json(OUT / "occurrence-manifest.json", {}) or {}
    _assert(document == recomputed, "exact occurrence audit is not a deterministic authority projection")
    _assert(document.get("occurrence_count") == 3303, "occurrence count")
    for field in (
        "invalid_occurrence_count", "missing_source_evidence_count",
        "duplicate_exact_key_count", "target_text_mismatch_count",
        "dangling_story_count",
    ):
        _assert(document.get(field) == 0, f"exact occurrence blocker: {field}")
    _assert(manifest.get("occurrence_count") == len(records), "occurrence manifest count")
    _assert(manifest.get("surface_only_selection_forbidden") is True, "surface-only selection is not forbidden")
    required = {"occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"}
    seen: set[tuple[Any, ...]] = set()
    for row in manifest.get("records", []):
        key = row.get("exact_occurrence_key")
        _assert(isinstance(key, Mapping), "missing exact occurrence key")
        _assert(required <= set(key), "incomplete exact occurrence key")
        identity = tuple(key.get(field) for field in ("mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"))
        _assert(identity not in seen, "duplicate exact occurrence key")
        seen.add(identity)
        _assert(row.get("validation_status") == "valid", f"invalid occurrence:{key.get('occurrence_id')}")
        _assert(row.get("target_text_matches") is True, f"source mismatch:{key.get('occurrence_id')}")
    _assert(len(seen) == 3303, "manifest exact key coverage")
    return {"occurrence_count": len(records), "exact_key_count": len(seen), "audit": document}


def validate(output: Path = OUT) -> dict[str, Any]:
    _assert(output == OUT, "validator is scoped to the F-prep output namespace")
    _assert(_git("rev-parse", "--abbrev-ref", "HEAD") == "main", "branch is not main")
    _assert(_git("rev-parse", BASELINE_COMMIT) == BASELINE_COMMIT, "required baseline is unavailable")
    _assert(file_hash(SC1_FROZEN) == EXPECTED_FROZEN_SC1_SHA256, "frozen SC1 hash changed")
    _assert(file_hash(SC1_CURRENT) == EXPECTED_CURRENT_SC1_SHA256, "current SC1 hash changed")
    _assert(file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json") == EXPECTED_IDENTITY_MANIFEST_SHA256, "identity freeze changed")
    _assert(file_hash(ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json") == EXPECTED_GOLD_SHA256, "active Gold changed")

    for name in OUTPUT_FILES:
        _assert((output / name).is_file(), f"missing F-prep output:{name}")
    for name in ("manifest.json", "architecture.json", "schemas.json", "protected-hashes.json"):
        _assert((FROZEN_OUT / name).is_file(), f"missing semantic freeze output:{name}")

    manifest = read_json(FROZEN_OUT / "manifest.json", {}) or {}
    architecture = read_json(FROZEN_OUT / "architecture.json", {}) or {}
    schemas = read_json(FROZEN_OUT / "schemas.json", {}) or {}
    protected_document = read_json(FROZEN_OUT / "protected-hashes.json", {}) or {}
    _assert(manifest.get("baseline_commit") == BASELINE_COMMIT, "semantic freeze baseline")
    _assert(manifest.get("status") == "QUALIFIED_ARCHITECTURE_FROZEN", "semantic freeze status")
    _assert(architecture.get("stage") == "SFH2.2-F-prep", "architecture stage")
    _assert(architecture.get("occurrence_provenance", {}).get("status") == "QUALIFIED", "provenance qualification")
    _assert(architecture.get("occurrence_multiclass", {}).get("source_stage") == "SFH2.2-A2OR", "A2OR not frozen as primary")
    _assert(architecture.get("boundary_validator", {}).get("source_stage") == "SFH2.2-A2OVB", "A2OVB not frozen")
    _assert(architecture.get("boundary_validator", {}).get("primary_blind") is True, "boundary validator blindness")
    excluded = architecture.get("excluded_components", {}).get("a2ov_primary_aware_reviewer", {})
    _assert(excluded.get("included_in_production") is False, "A2OV reviewer was not excluded")
    _assert(architecture.get("excluded_components", {}).get("old_monolithic_occurrence_role", {}).get("semantic_authority") is False, "old role remained authority")
    _assert(architecture.get("safety_invariants", {}).get("candidate_only") is True, "candidate safety")
    _assert(architecture.get("safety_invariants", {}).get("canonical_write_back") is False, "write-back safety")
    _assert(schemas.get("candidate_semantic_occurrence", {}).get("additionalProperties") is False, "candidate schema is not closed")
    _assert(schemas.get("a2ovb_boundary_output", {}).get("primary_label_forbidden_in_packet") is True, "boundary packet blindness schema")

    occurrence_info = _validate_exact_occurrences()
    scope = read_json(output / "production-scope.json", {}) or {}
    _assert(scope.get("total_stories") == 188, "derived Story scope")
    _assert(scope.get("eligible_story_count") == 188, "eligible Story scope")
    _assert(scope.get("published_runtime_story_count") == 143, "published runtime scope")
    _assert(scope.get("research_only_story_count") == 45, "research-only scope")
    _assert(scope.get("historical_188_scope_confirmed") is True, "188-story scope was not confirmed")
    _assert(scope.get("total_validated_occurrences") == 3303, "scope occurrence count")
    _assert(scope.get("occurrence_counts_by_source_layer") == {"liu_annotation": 2021, "main_text": 1282}, "source-layer scope counts")

    readiness = read_json(output / "identity-readiness.json", {}) or {}
    counts = readiness.get("counts", {})
    _assert(sum(int(value) for value in counts.values()) == 3303, "identity readiness partition")
    _assert(counts.get("identity_ready") == 26, "exact frozen identity reuse count")
    _assert(counts.get("identity_requires_pipeline") == 2842, "identity pipeline count")
    _assert(counts.get("identity_not_applicable") == 435, "identity non-applicable count")
    _assert(counts.get("identity_blocked", 0) == 0, "identity blockers")

    dag = read_json(output / "production-dag.json", {}) or {}
    node_ids = {node.get("id") for node in dag.get("nodes", []) if isinstance(node, Mapping)}
    _assert("a2or_primary" in node_ids and "a2ovb_boundary" in node_ids, "qualified occurrence nodes")
    _assert("a2ov" not in node_ids, "excluded A2OV appears in production DAG")
    _assert(dag.get("a2ov_excluded") is True and dag.get("old_occurrence_role_is_not_authority") is True, "DAG boundary flags")

    cache = read_json(output / "cache-reuse-plan.json", {}) or {}
    _assert(cache.get("exact_reusable_provider_result_count") == 41, "qualified cache candidate count")
    _assert(cache.get("counts_by_stage") == {"boundary_validator": 15, "occurrence_primary": 26}, "qualified cache stage counts")
    _assert(cache.get("policy", {}).get("reuse_requires_all_components") is True, "strict cache policy")
    _assert(cache.get("policy", {}).get("case_id_surface_story_only_reuse_forbidden") is True, "weak cache key not forbidden")
    for entry in cache.get("entries", []):
        _assert(entry.get("exact_reuse_candidate") is True, "cache entry not exact")
        _assert(entry.get("reuse_requires_current_request_hash_equality") is True, "cache request hash guard")
        _assert(entry.get("request_hash") and entry.get("exact_request_witness_present") is True, "cache request witness")
        _assert(len(entry.get("matching_key_fields", [])) == 6, "cache occurrence matching fields")

    preflight = read_json(output / "preflight-validation.json", {}) or {}
    _assert(preflight.get("baseline_commit") == BASELINE_COMMIT, "preflight baseline")
    _assert(preflight.get("provider_calls") == 0 and preflight.get("provider_api_calls") == 0, "F-prep provider calls")
    _assert(preflight.get("scope_valid") is True, "scope preflight")
    _assert(preflight.get("exact_occurrence_integrity_failures") == 0, "occurrence preflight")
    _assert(preflight.get("identity_blocked_count") == 0, "identity preflight")
    _assert(preflight.get("no_full_corpus_live_run") is True, "full corpus was run")

    recommendation = read_json(output / "recommendation.json", {}) or {}
    _assert(recommendation.get("recommendation") == "sfh2_f1_bounded_wave_ready", "F1 readiness recommendation")
    _assert(recommendation.get("next_stage") == "SFH2.2-F1", "next stage")
    f1 = read_json(output / "f1-selection.json", {}) or {}
    _assert(f1.get("not_executed") is True and f1.get("gold_used_for_selection") is False, "F1 selection safety")
    _assert(0 < f1.get("occurrence_count", 0) <= 30, "F1 bound")
    f1_keys = []
    for row in f1.get("records", []):
        key = row.get("exact_occurrence_key")
        _assert(isinstance(key, Mapping), "F1 exact key")
        f1_keys.append(tuple(key.get(field) for field in ("mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface")))
        _assert(row.get("gold_used_for_selection") is False, "F1 Gold leakage")
    _assert(len(f1_keys) == len(set(f1_keys)), "F1 duplicate exact keys")

    for path in (FROZEN_OUT / "manifest.json", FROZEN_OUT / "architecture.json", FROZEN_OUT / "schemas.json", FROZEN_OUT / "protected-hashes.json", *[output / name for name in OUTPUT_FILES]):
        _validate_candidate_flags(read_json(path, {}), str(path.relative_to(ROOT)))
    _assert(not [path for path in (output).rglob("*") if path.is_file() and "raw-api" in path.as_posix()], "raw provider output under F-prep")

    current_protected = protected_hashes()
    _assert(protected_document.get("files") == current_protected.get("files"), "protected file witness drift")
    _assert(protected_document.get("trees") == current_protected.get("trees"), "protected tree witness drift")
    _assert(protected_document.get("files", {}).get("data/derived/sc1-site.json", {}).get("sha256") == EXPECTED_FROZEN_SC1_SHA256, "frozen SC1 witness")
    _assert(protected_document.get("files", {}).get("data/derived/sc1-current-site.json", {}).get("sha256") == EXPECTED_CURRENT_SC1_SHA256, "current SC1 witness")

    growth = audit_repository(ROOT, baseline=BASELINE_COMMIT, include_untracked=True)
    _assert(not growth.get("artifact_policy_violations"), "new C3 artifact-policy violation")

    allowed_prefixes = (
        "data/generated/sfh2-f-prep/", "data/frozen/sfh2/semantic-v1/",
        "scripts/sfh2_f_prep/", "scripts/run_sfh2_f_prep.py", "scripts/validate_sfh2_f_prep.py",
        "tests/test_sfh2_f_prep.py", "docs/sfh2-f-prep-", "package.json",
        "data/derived/test-suite-classification-c1.json",
    )
    unexpected = [path for path in _status_paths() if not path.startswith(allowed_prefixes)]
    _assert(not unexpected, "unexpected worktree changes:" + repr(unexpected))

    return {
        "schema": "sfh2-f-prep-validator-v1",
        "valid": True,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git("rev-parse", "HEAD"),
        "baseline_commit": BASELINE_COMMIT,
        "provider_calls": 0,
        "scope_stories": scope.get("total_stories"),
        "occurrences": occurrence_info["occurrence_count"],
        "identity_readiness": counts,
        "exact_cache_candidates": cache.get("exact_reusable_provider_result_count"),
        "f1_occurrences": f1.get("occurrence_count"),
        "recommendation": recommendation.get("recommendation"),
        "c3_status": growth.get("policy_status"),
        "protected_hashes_valid": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate(args.output), ensure_ascii=False, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"SFH2.2-F-prep validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
