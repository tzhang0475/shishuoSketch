#!/usr/bin/env python3
"""Validate the offline SFH2.2-A2OS occurrence-alignment audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2os.common import (
    BASELINE_COMMIT,
    CASE_COUNT,
    GOLD_PATH,
    IDENTITY_MANIFEST_PATH,
    OUT,
    PROTECTED_IDENTITY_SHA256,
    PROTECTED_SC1_CURRENT_SHA256,
    PROTECTED_SC1_SHA256,
    ROOT,
    file_hash,
)


REQUIRED_OUTPUTS = (
    "architecture.json",
    "exact-occurrence-audit.json",
    "duplicate-surface-audit.json",
    "selection-intent-alignment.json",
    "gold-alignment-audit.json",
    "gold-review-candidates.json",
    "residual-model-errors.json",
    "counterfactual-evaluation.json",
    "metrics.json",
    "recommendation.json",
)

PROTECTED_PREFIXES = (
    "data/generated/sfh2-a2o/",
    "data/generated/sfh2-a2ot/",
    "data/generated/sfh2-a2or/",
    "data/generated/sfh2-a2g/",
    "data/generated/sfh2-a2gr/",
)
PROTECTED_FILES = (
    "data/annotation/sfh2-a2o-evaluation-gold.json",
    "data/generated/sfh1/story-packets.json",
    "data/generated/sfh1/validated-mentions.json",
    "data/people.json",
    "data/aliases.json",
    "data/derived/sc1-site.json",
    "data/derived/sc1-current-site.json",
    "data/frozen/sfh2/identity-v1/manifest.json",
)


def _git_bytes(root: Path, commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout if result.returncode == 0 else b""


def _git_paths(root: Path, commit: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line]


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _protected_hash_errors(root: Path) -> list[str]:
    errors: list[str] = []
    baseline_paths = set(_git_paths(root, BASELINE_COMMIT))
    paths = set(PROTECTED_FILES)
    paths.update(path for path in baseline_paths if path.startswith(PROTECTED_PREFIXES))
    for path in sorted(paths):
        expected = _git_bytes(root, BASELINE_COMMIT, path)
        current_path = root / path
        if not expected:
            continue
        if not current_path.is_file():
            errors.append(f"protected_missing:{path}")
        elif current_path.read_bytes() != expected:
            errors.append(f"protected_changed:{path}")
    return errors


def validate(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    out = root / "data/generated/sfh2-a2os"
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
    ).stdout.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"], cwd=root, check=False
    ).returncode == 0
    if branch != "main":
        errors.append(f"wrong_branch:{branch}")
    if not ancestor:
        errors.append("baseline_not_ancestor")

    documents: dict[str, Any] = {}
    for name in REQUIRED_OUTPUTS:
        path = out / name
        if not path.is_file():
            errors.append(f"missing_output:{name}")
            continue
        try:
            documents[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_json:{name}:{exc}")

    exact = documents.get("exact-occurrence-audit.json", {})
    exact_records = exact.get("records", []) if isinstance(exact, Mapping) else []
    if len(exact_records) != CASE_COUNT:
        errors.append("exact_case_count_invalid")
    if not all(row.get("integrity", {}).get("structural_valid") is True for row in exact_records if isinstance(row, Mapping)):
        errors.append("exact_occurrence_integrity_failure")
    if not all(row.get("gold_basis_used_for_target_resolution") is False for row in exact_records if isinstance(row, Mapping)):
        errors.append("gold_basis_used_for_target_resolution")
    case_ids = [row.get("case_id") for row in exact_records if isinstance(row, Mapping)]
    if len(case_ids) != len(set(case_ids)):
        errors.append("duplicate_case_ids")

    selection_alignment = documents.get("selection-intent-alignment.json", {})
    if selection_alignment.get("case_count") != CASE_COUNT:
        errors.append("selection_alignment_case_count_invalid")
    if selection_alignment.get("counts") != {"aligned": 25, "misaligned": 1}:
        errors.append("selection_alignment_counts_unexpected")
    if selection_alignment.get("historical_mention_id_pinned") is not False:
        errors.append("historical_selector_pin_claim_invalid")
    if selection_alignment.get("prospective_rule_is_selection_integrity_only") is not True:
        errors.append("prospective_rule_boundary_invalid")

    duplicate = documents.get("duplicate-surface-audit.json", {})
    if duplicate.get("exact_validated_tuple_duplicate_group_count") != 0:
        errors.append("unexpected_exact_tuple_duplicate")
    if duplicate.get("textually_repeated_or_overlapping_case_count") != 10:
        errors.append("textual_collision_count_unexpected")

    candidates = documents.get("gold-review-candidates.json", {})
    candidate_rows = candidates.get("records", []) if isinstance(candidates, Mapping) else []
    candidate_ids = {row.get("case_id") for row in candidate_rows if isinstance(row, Mapping)}
    if candidate_ids != {
        "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773",
        "sfh2-a0-57d1fc3c0492b21ee1f4",
    }:
        errors.append("gold_candidate_case_set_invalid")
    if any(row.get("gold_mutation_performed") is not False or row.get("human_review_required") is not True for row in candidate_rows if isinstance(row, Mapping)):
        errors.append("gold_candidate_mutation_or_review_flag_invalid")

    residual = documents.get("residual-model-errors.json", {})
    if residual.get("remaining_genuine_model_error_count") != 2:
        errors.append("residual_model_error_count_unexpected")
    if set(residual.get("known_residual_cases", [])) != {
        "sfh2-a0r-l-challenge-f56a3b1584f60d143182",
        "sfh2-a0r-l-challenge-a1f887b7602c151cfbbd",
    }:
        errors.append("residual_model_error_case_set_invalid")

    counterfactual = documents.get("counterfactual-evaluation.json", {})
    scenarios = counterfactual.get("scenarios", []) if isinstance(counterfactual, Mapping) else []
    if not scenarios or scenarios[0].get("score", {}).get("all", {}).get("correct") != 22:
        errors.append("current_a2or_counterfactual_invalid")
    if not scenarios or scenarios[-1].get("score", {}).get("all", {}).get("correct") != 24:
        errors.append("all_candidate_counterfactual_invalid")

    metrics = documents.get("metrics.json", {})
    if metrics.get("provider_calls") != 0 or metrics.get("exact_occurrence_spans_valid") != CASE_COUNT:
        errors.append("offline_or_occurrence_metric_invalid")
    if metrics.get("current_a2or", {}).get("correct") != 22:
        errors.append("current_a2or_metric_invalid")

    recommendation = documents.get("recommendation.json", {})
    if recommendation.get("recommendation") != "sfh2_occurrence_gold_alignment_review_required":
        errors.append("recommendation_invalid")

    for path in (root / "scripts/sfh2_a2os").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"surface\s*(?:==|!=)|surface\s+in\b", source):
            errors.append(f"surface_specific_semantic_rule:{path.name}")
        if re.search(r"(?:DEEPSEEK_API_KEY|api\.deepseek\.com|requests|urllib|openai)", source, re.IGNORECASE):
            errors.append(f"provider_path_in_offline_audit:{path.name}")

    errors.extend(_protected_hash_errors(root))
    sc1 = root / "data/derived/sc1-site.json"
    sc1_current = root / "data/derived/sc1-current-site.json"
    identity = root / "data/frozen/sfh2/identity-v1/manifest.json"
    if not sc1.is_file() or file_hash(sc1) != PROTECTED_SC1_SHA256:
        errors.append("sc1_frozen_hash_changed")
    if not sc1_current.is_file() or file_hash(sc1_current) != PROTECTED_SC1_CURRENT_SHA256:
        errors.append("sc1_current_hash_changed")
    if not identity.is_file() or file_hash(identity) != PROTECTED_IDENTITY_SHA256:
        errors.append("identity_manifest_hash_changed")
    gold_relative = str(GOLD_PATH.relative_to(root))
    if not GOLD_PATH.is_file() or GOLD_PATH.read_bytes() != _git_bytes(root, BASELINE_COMMIT, gold_relative):
        errors.append("current_gold_changed")
    for dirname in (out / "raw-api", out / "provider-responses"):
        if dirname.exists() and any(path.is_file() for path in dirname.rglob("*")):
            errors.append(f"raw_provider_artifact_present:{dirname.name}")

    return {
        "schema": "sfh2-a2os-validator-v1",
        "stage": "SFH2.2-A2OS",
        "baseline_commit": BASELINE_COMMIT,
        "current_head": current_head,
        "branch": branch,
        "provider_calls": 0,
        "case_count": len(exact_records),
        "gold_mutated": False,
        "protected_historical_inputs_unchanged": not any(item.startswith("protected_") for item in errors),
        "errors": sorted(set(errors)),
        "valid": not errors,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = validate(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
