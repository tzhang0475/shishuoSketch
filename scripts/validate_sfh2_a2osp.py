#!/usr/bin/env python3
"""Validate the offline SFH2.2-A2OSP Gold promotion contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2osp.common import (
    A2O_ROOT,
    A2OR_ROOT,
    A2OS_ROOT,
    A2OT_ROOT,
    AUTHORITY_PATH,
    BASELINE_COMMIT,
    CASE_COUNT,
    CASE_GU,
    CASE_QI,
    CURRENT_SC1_SHA256,
    EXPECTED_CHANGED_CASES,
    FROZEN_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_PATH,
    IDENTITY_MANIFEST_SHA256,
    OUT,
    PREVIOUS_GOLD_SHA256,
    ROOT,
    changed_fields,
    file_hash,
    load_inputs,
    occurrence_key,
    text,
)


REQUIRED_OUTPUTS = (
    "reviewed-gold-delta.json",
    "a2or-post-promotion-evaluation.json",
    "residual-error-qualification.json",
    "single-historian-assessment.json",
    "selection-integrity-invariant.json",
    "metrics.json",
    "recommendation.json",
)
PROTECTED_TREE_PREFIXES = (
    "data/generated/sfh2-a2o/",
    "data/generated/sfh2-a2ot/",
    "data/generated/sfh2-a2or/",
    "data/generated/sfh2-a2os/",
)
PROTECTED_FILES = (
    "data/frozen/sfh2/identity-v1/manifest.json",
    "data/derived/sc1-site.json",
    "data/derived/sc1-current-site.json",
    "data/people.json",
    "data/aliases.json",
)


def _read(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _git_bytes(path: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{path}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _git_paths(prefix: str) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", BASELINE_COMMIT, "--", prefix],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return [line for line in completed.stdout.splitlines() if line]


def _tree_unchanged(prefix: str, errors: list[str]) -> bool:
    paths = _git_paths(prefix)
    unchanged = True
    for relative in paths:
        path = ROOT / relative
        expected = _git_bytes(relative)
        if expected is None or not path.is_file() or path.read_bytes() != expected:
            errors.append(f"protected_historical_artifact_changed:{relative}")
            unchanged = False
    return unchanged


def _walk_flags(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        if "candidate_only" in value and value["candidate_only"] is not True:
            errors.append(f"{path}.candidate_only_not_true")
        if "canonical_write_back" in value and value["canonical_write_back"] is not False:
            errors.append(f"{path}.canonical_write_back_not_false")
        for key, child in value.items():
            errors.extend(_walk_flags(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_walk_flags(child, f"{path}[{index}]"))
    return errors


def _authority_errors(inputs: Mapping[str, Any], errors: list[str]) -> None:
    authority = inputs["authority"]
    records = authority.get("records", []) if isinstance(authority, Mapping) else []
    if authority.get("authority") != "human_semantic_review":
        errors.append("authority_not_human_review")
    if authority.get("predecessor_stage") != "SFH2.2-A2OS":
        errors.append("authority_predecessor_invalid")
    if authority.get("review_status") != "reviewed":
        errors.append("authority_not_reviewed")
    if authority.get("canonical_write_back") is not False or authority.get("candidate_only") is not False:
        errors.append("authority_storage_boundary_invalid")
    if authority.get("previous_gold_sha256") != PREVIOUS_GOLD_SHA256:
        errors.append("authority_previous_gold_hash_invalid")
    if authority.get("new_gold_sha256") != file_hash(GOLD_PATH):
        errors.append("authority_new_gold_hash_invalid")
    if authority.get("substantive_gold_mutation_count") != 2 or authority.get("unchanged_gold_record_count") != 24:
        errors.append("authority_mutation_counts_invalid")
    ids = [text(row.get("case_id")) for row in records if isinstance(row, Mapping)]
    if set(ids) != set(EXPECTED_CHANGED_CASES) or len(ids) != 2:
        errors.append("authority_case_set_invalid")
    exact_by_case = {text(row.get("case_id")): row for row in inputs["exact"].values()}
    for row in records:
        if not isinstance(row, Mapping):
            errors.append("authority_record_not_object")
            continue
        case_id = text(row.get("case_id"))
        if row.get("authority") != "human_semantic_review" or row.get("predecessor_stage") != "SFH2.2-A2OS":
            errors.append(f"authority_record_metadata_invalid:{case_id}")
        if row.get("canonical_write_back") is not False or row.get("review_status") != "reviewed":
            errors.append(f"authority_record_boundary_invalid:{case_id}")
        if row.get("exact_occurrence_key") != occurrence_key(exact_by_case.get(case_id, {})):
            errors.append(f"authority_exact_key_invalid:{case_id}")
    if not isinstance(inputs.get("active_gold"), Mapping):
        errors.append("active_gold_missing")


def _gold_errors(inputs: Mapping[str, Any], errors: list[str]) -> None:
    before = inputs["frozen_gold"]
    after = inputs["active_gold"]
    changed = [case_id for case_id in before if before[case_id] != after.get(case_id)]
    if changed != list(EXPECTED_CHANGED_CASES):
        errors.append(f"gold_changed_case_set_invalid:{changed}")
    unchanged = [case_id for case_id in before if case_id not in changed and before[case_id] == after.get(case_id)]
    if len(unchanged) != CASE_COUNT - 2:
        errors.append("gold_unchanged_record_count_invalid")
    expected = {
        CASE_GU: ("participant", "scene_participant"),
        CASE_QI: ("reference", "annotation_person"),
    }
    for case_id, (function, role) in expected.items():
        if after.get(case_id, {}).get("expected_narrative_function") != function or after.get(case_id, {}).get("expected_legacy_occurrence_role") != role:
            errors.append(f"promoted_gold_label_invalid:{case_id}")
    document = _read(GOLD_PATH, {}) or {}
    metadata = document.get("gold_revision", {})
    if metadata.get("stage") != "SFH2.2-A2OSP" or metadata.get("previous_sha256") != PREVIOUS_GOLD_SHA256 or metadata.get("substantive_mutation_count") != 2:
        errors.append("gold_revision_metadata_invalid")
    if file_hash(GOLD_PATH) == PREVIOUS_GOLD_SHA256:
        errors.append("gold_was_not_promoted")


def _output_errors(inputs: Mapping[str, Any], errors: list[str]) -> None:
    documents: dict[str, Any] = {}
    for name in REQUIRED_OUTPUTS:
        path = OUT / name
        if not path.is_file():
            errors.append(f"missing_output:{name}")
            continue
        try:
            documents[name] = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_output:{name}:{exc}")
    evaluation = documents.get("a2or-post-promotion-evaluation.json", {})
    post = evaluation.get("post_promotion_metrics", {}) if isinstance(evaluation, Mapping) else {}
    pre = evaluation.get("pre_promotion_metrics", {}) if isinstance(evaluation, Mapping) else {}
    if evaluation.get("case_count") != CASE_COUNT or len(evaluation.get("records", [])) != CASE_COUNT:
        errors.append("evaluation_case_count_invalid")
    if pre.get("narrative_function", {}).get("correct") != 22:
        errors.append("pre_promotion_score_invalid")
    if post.get("narrative_function", {}).get("correct") != 24 or post.get("narrative_function", {}).get("evaluable") != CASE_COUNT:
        errors.append("post_promotion_score_invalid")
    if post.get("resolution_coverage", {}).get("accuracy") != 1.0:
        errors.append("resolution_coverage_invalid")
    if post.get("provenance", {}).get("accuracy") != 1.0 or post.get("identity_preservation", {}).get("accuracy") != 1.0:
        errors.append("frozen_axis_accuracy_invalid")
    residual = documents.get("residual-error-qualification.json", {})
    if residual.get("qualified_genuine_error_count") != 2 or residual.get("error_family_counts") != {"reference_to_participant_overreach": 2}:
        errors.append("residual_qualification_invalid")
    if not all(all(row.get("qualification_checks", {}).values()) and row.get("qualified_as_genuine_semantic_error") is True for row in residual.get("records", [])):
        errors.append("residual_checks_invalid")
    assessment = documents.get("single-historian-assessment.json", {})
    if assessment.get("single_historian_fully_qualified") is not False or assessment.get("high_confidence_systematic_boundary_error") is not True:
        errors.append("single_historian_assessment_invalid")
    selection = documents.get("selection-integrity-invariant.json", {})
    if selection.get("historical_selector_rewritten") is not False or selection.get("python_may_infer_semantic_role_from_offsets") is not False:
        errors.append("selection_integrity_boundary_invalid")
    recommendation = documents.get("recommendation.json", {})
    if recommendation.get("recommendation") != "sfh2_occurrence_semantic_reviewer_test_required" or recommendation.get("next_stage") != "SFH2.2-A2OV":
        errors.append("recommendation_invalid")
    for name, document in documents.items():
        if name.endswith(".json"):
            errors.extend(f"unsafe_output:{name}:{issue}" for issue in _walk_flags(document))
    if (OUT / "raw-api").exists() or (OUT / "provider-responses").exists():
        errors.append("raw_provider_output_present")


def validate(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False).stdout.strip()
    if branch != "main":
        errors.append(f"wrong_branch:{branch}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"], cwd=root, check=False).returncode:
        errors.append("baseline_not_ancestor")
    try:
        inputs = load_inputs()
    except (OSError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        return {
            "schema": "sfh2-a2osp-validator-v1",
            "baseline_commit": BASELINE_COMMIT,
            "errors": [f"input_load_failure:{exc}"],
            "valid": False,
            "provider_calls": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        }
    _authority_errors(inputs, errors)
    _gold_errors(inputs, errors)
    _output_errors(inputs, errors)
    for prefix in PROTECTED_TREE_PREFIXES:
        _tree_unchanged(prefix, errors)
    for relative in PROTECTED_FILES:
        expected = _git_bytes(relative)
        path = root / relative
        if expected is None or not path.is_file() or path.read_bytes() != expected:
            errors.append(f"protected_file_changed:{relative}")
    if not (root / "scripts/sfh2_a0r_l/selection.py").read_bytes() == (_git_bytes("scripts/sfh2_a0r_l/selection.py") or b""):
        errors.append("historical_selector_changed")
    for path in (root / "scripts/sfh2_a2osp").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"surface\s*(?:==|!=|in\b)", source):
            errors.append(f"surface_specific_semantic_rule:{path.name}")
    metrics = _read(OUT / "metrics.json", {}) or {}
    if metrics.get("provider_calls") != 0:
        errors.append("provider_calls_nonzero")
    return {
        "schema": "sfh2-a2osp-validator-v1",
        "baseline_commit": BASELINE_COMMIT,
        "current_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False).stdout.strip(),
        "case_count": CASE_COUNT,
        "gold_mutations": 2,
        "provider_calls": 0,
        "historical_outputs_unchanged": not any(error.startswith("protected_historical_artifact_changed:") for error in errors),
        "errors": sorted(set(errors)),
        "valid": not errors,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = validate(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
