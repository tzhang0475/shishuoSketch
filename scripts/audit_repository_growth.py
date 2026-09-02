#!/usr/bin/env python3
"""Audit prospective generated-artifact growth without changing the repository.

The audit compares the current tracked/worktree paths with a caller-supplied
Git baseline. Paths already present in that baseline are grandfathered: their
historical policy status is reported, but it cannot fail the prospective
current-CI guard. New paths are classified by the lifecycle policy and only
new policy violations make ``--check-new`` fail.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config/generated-artifact-policy.json"


def _normalise(path: str) -> str:
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError(f"policy must be an object: {path}")
    for key in ("generated_roots", "classes", "thresholds", "path_classifications", "allowed_exceptions"):
        if key not in document:
            raise ValueError(f"policy missing {key}: {path}")
    return document


def _generated_roots(policy: Mapping[str, Any]) -> tuple[str, ...]:
    roots = []
    for raw in policy.get("generated_roots", []):
        if not isinstance(raw, str):
            raise ValueError("generated_roots must contain strings")
        root = _normalise(raw).rstrip("/") + "/"
        roots.append(root)
    return tuple(roots)


def is_generated_path(path: str, policy: Mapping[str, Any]) -> bool:
    normalised = _normalise(path)
    return any(normalised.startswith(root) for root in _generated_roots(policy))


def _matches(pattern: str, path: str) -> bool:
    return fnmatch.fnmatchcase(_normalise(path), _normalise(pattern))


def is_raw_provider_path(path: str) -> bool:
    """Recognize transport directory conventions, not historical semantics."""

    normalised = _normalise(path).lower()
    segments = set(normalised.split("/"))
    raw_segments = {
        "raw-api",
        "raw_api",
        "provider-response",
        "provider-responses",
        "provider_response",
        "provider_responses",
        "http-response",
        "http-responses",
        "http_response",
        "http_responses",
    }
    return bool(segments & raw_segments)


def classify_path(path: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    normalised = _normalise(path)
    if not is_generated_path(normalised, policy):
        return {
            "artifact_class": None,
            "explicit": False,
            "classification_source": "not_generated",
        }
    for row in policy.get("path_classifications", []):
        if not isinstance(row, Mapping):
            raise ValueError("path_classifications must contain objects")
        pattern = row.get("pattern")
        artifact_class = row.get("artifact_class")
        if isinstance(pattern, str) and isinstance(artifact_class, str) and _matches(pattern, normalised):
            return {
                "artifact_class": artifact_class,
                "explicit": bool(row.get("explicit")),
                "classification_source": "path_classification",
                "matched_pattern": pattern,
            }
    default_policy = policy.get("default_git_policy", {})
    return {
        "artifact_class": default_policy.get("unclassified_generated_default_class", "GIT_COMPACT_RESULT"),
        "explicit": bool(default_policy.get("unclassified_generated_is_explicit", False)),
        "classification_source": "default_generated_class",
    }


def _current_paths(root: Path, include_untracked: bool) -> tuple[set[str], set[str]]:
    tracked = {
        _normalise(path.decode("utf-8"))
        for path in _git(root, "ls-files", "-z").encode("utf-8").split(b"\0")
        if path
    }
    untracked: set[str] = set()
    if include_untracked:
        untracked = {
            _normalise(path.decode("utf-8"))
            for path in _git(root, "ls-files", "--others", "--exclude-standard", "-z").encode("utf-8").split(b"\0")
            if path
        }
    return tracked, untracked


def _baseline_sizes(root: Path, baseline: str) -> dict[str, int]:
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", "-l", "-z", "--full-tree", baseline],
        cwd=root,
    )
    result: dict[str, int] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        fields = header.split()
        if len(fields) != 4 or fields[1] != b"blob":
            continue
        result[_normalise(raw_path.decode("utf-8"))] = int(fields[3])
    return result


def _file_size(root: Path, relative_path: str) -> int:
    path = root / relative_path
    if path.is_symlink():
        return len(os.readlink(path).encode("utf-8"))
    return path.stat().st_size


def _exception_for(path: str, policy: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for exception in policy.get("allowed_exceptions", []):
        if not isinstance(exception, Mapping):
            raise ValueError("allowed_exceptions must contain objects")
        pattern = exception.get("path_or_pattern")
        if isinstance(pattern, str) and _matches(pattern, path):
            return exception
    return None


def _exception_is_valid(exception: Mapping[str, Any]) -> bool:
    required = ("id", "path_or_pattern", "artifact_class", "reason", "review_reference")
    return all(isinstance(exception.get(key), str) and exception.get(key) for key in required)


def _policy_observations(
    path: str,
    size_bytes: int,
    policy: Mapping[str, Any],
    *,
    is_new: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    classification = classify_path(path, policy)
    exception = _exception_for(path, policy)
    artifact_class = classification.get("artifact_class")
    explicit = bool(classification.get("explicit"))
    if exception is not None and isinstance(exception.get("artifact_class"), str):
        artifact_class = exception["artifact_class"]
        explicit = True

    thresholds = policy.get("thresholds", {})
    warn_bytes = int(thresholds.get("warn_generated_file_bytes", 0))
    explicit_bytes = int(thresholds.get("require_explicit_classification_bytes", 0))
    warning: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    if size_bytes > warn_bytes:
        warning.append({
            "code": "large_generated_file_warning",
            "path": path,
            "size_bytes": size_bytes,
            "threshold_bytes": warn_bytes,
            "new": is_new,
        })

    if not is_new:
        return {
            "path": path,
            "size_bytes": size_bytes,
            "artifact_class": artifact_class,
            "explicit_classification": explicit,
            "classification_source": classification.get("classification_source"),
            "exception_id": exception.get("id") if exception else None,
            "grandfathered": True,
        }, warning, violations

    if size_bytes > explicit_bytes and not explicit:
        violations.append({
            "code": "new_large_generated_file_without_explicit_classification",
            "path": path,
            "size_bytes": size_bytes,
            "threshold_bytes": explicit_bytes,
            "artifact_class": artifact_class,
            "reason": "new generated files above the explicit-classification threshold require a policy classification or approved exception",
        })

    requires_exception = artifact_class in {"EXTERNAL_ARCHIVE_DEFAULT", "EPHEMERAL_REBUILDABLE"}
    if requires_exception and not _exception_is_valid(exception or {}):
        violations.append({
            "code": "new_generated_artifact_requires_approved_exception",
            "path": path,
            "size_bytes": size_bytes,
            "artifact_class": artifact_class,
            "reason": "this artifact class is not committed to Git by default",
        })
    if is_raw_provider_path(path) and not _exception_is_valid(exception or {}):
        if not any(item["code"] == "new_generated_artifact_requires_approved_exception" for item in violations):
            violations.append({
                "code": "new_raw_provider_payload_without_approved_exception",
                "path": path,
                "size_bytes": size_bytes,
                "artifact_class": artifact_class,
                "reason": "raw provider/API payloads require explicit archive exception metadata",
            })

    return {
        "path": path,
        "size_bytes": size_bytes,
        "artifact_class": artifact_class,
        "explicit_classification": explicit,
        "classification_source": classification.get("classification_source"),
        "matched_pattern": classification.get("matched_pattern"),
        "exception_id": exception.get("id") if exception else None,
        "grandfathered": False,
    }, warning, violations


def audit_repository(
    root: Path = ROOT,
    *,
    baseline: str,
    policy_path: Path = DEFAULT_POLICY_PATH,
    include_untracked: bool = True,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    resolved_baseline = _git(root, "rev-parse", baseline).strip()
    current_head = _git(root, "rev-parse", "HEAD").strip()
    baseline_sizes = _baseline_sizes(root, baseline)
    tracked, untracked = _current_paths(root, include_untracked)
    current_paths = tracked | untracked
    current_sizes = {path: _file_size(root, path) for path in current_paths if (root / path).exists() or (root / path).is_symlink()}

    generated_current = {path for path in current_sizes if is_generated_path(path, policy)}
    generated_baseline = {path for path in baseline_sizes if is_generated_path(path, policy)}
    new_generated = sorted(generated_current - set(baseline_sizes))
    changed_generated = sorted(
        path for path in generated_current & set(baseline_sizes)
        if current_sizes[path] != baseline_sizes[path]
    )
    removed_generated = sorted(generated_baseline - generated_current)

    observations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for path in sorted(generated_current):
        observation, path_warnings, path_violations = _policy_observations(
            path,
            current_sizes[path],
            policy,
            is_new=path in new_generated,
        )
        observations.append(observation)
        warnings.extend(path_warnings)
        violations.extend(path_violations)

    large_files = [item for item in warnings]
    new_raw = [path for path in new_generated if is_raw_provider_path(path)]
    new_large = [item for item in large_files if item["new"]]
    grandfathered = [item for item in observations if item["grandfathered"]]

    baseline_tracked_bytes = sum(size for path, size in baseline_sizes.items())
    current_tracked_bytes = sum(current_sizes[path] for path in tracked)
    new_generated_bytes = sum(current_sizes[path] for path in new_generated)
    positive_changed_bytes = sum(
        max(0, current_sizes[path] - baseline_sizes[path]) for path in changed_generated
    )
    report = {
        "schema": "repository-growth-audit-v1",
        "non_mutating": True,
        "baseline_ref": baseline,
        "baseline_commit": resolved_baseline,
        "current_head": current_head,
        "include_untracked_nonignored": include_untracked,
        "tracked_file_count": len(tracked),
        "tracked_bytes": current_tracked_bytes,
        "baseline_tracked_file_count": len(baseline_sizes),
        "baseline_tracked_bytes": baseline_tracked_bytes,
        "tracked_byte_delta": current_tracked_bytes - baseline_tracked_bytes,
        "generated_roots": list(_generated_roots(policy)),
        "generated_file_count": len(generated_current),
        "new_generated_file_count": len(new_generated),
        "new_generated_bytes": new_generated_bytes,
        "changed_generated_file_count": len(changed_generated),
        "positive_changed_generated_bytes": positive_changed_bytes,
        "removed_generated_file_count": len(removed_generated),
        "new_generated_files": new_generated,
        "changed_generated_files": [
            {
                "path": path,
                "baseline_size_bytes": baseline_sizes[path],
                "current_size_bytes": current_sizes[path],
                "delta_bytes": current_sizes[path] - baseline_sizes[path],
            }
            for path in changed_generated
        ],
        "removed_generated_files": removed_generated,
        "large_generated_files": large_files,
        "new_large_generated_files": new_large,
        "new_raw_provider_files": new_raw,
        "grandfathered_existing_generated_files": grandfathered,
        "artifact_policy_violations": violations,
        "warnings": warnings,
        "policy_status": "fail_new_violations" if violations else "pass_no_new_violations",
        "policy_path": str(policy_path.relative_to(root)) if policy_path.is_relative_to(root) else str(policy_path),
    }
    return report


def _print_report(report: Mapping[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="Git ref used to grandfather existing paths and measure growth")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--tracked-only", action="store_true", help="ignore non-ignored untracked worktree files")
    parser.add_argument("--check-new", action="store_true", help="fail only when new policy violations are found")
    args = parser.parse_args(argv)
    try:
        report = audit_repository(
            ROOT,
            baseline=args.baseline,
            policy_path=args.policy,
            include_untracked=not args.tracked_only,
        )
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
        print(f"repository growth audit error: {exc}", file=sys.stderr)
        return 2
    _print_report(report)
    if args.check_new and report["artifact_policy_violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
