#!/usr/bin/env python3
"""Validate D1.0 audit artifacts without modifying production data."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
from typing import Any

try:
    from .d1_0_common import (
        REQUIRED_TOP_LEVEL_FIELDS,
        build_bundle_audit,
        read_json,
        scan_dependencies,
        sha256_file,
    )
except ImportError:  # direct execution from the repository root
    from d1_0_common import (
        REQUIRED_TOP_LEVEL_FIELDS,
        build_bundle_audit,
        read_json,
        scan_dependencies,
        sha256_file,
    )


def _same(actual: Any, expected: Any, label: str, errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{label} differs from the current deterministic audit")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    audit_path = root / "data/derived/d1-0-bundle-size-audit.json"
    dependency_path = root / "data/derived/d1-0-dependency-audit.json"
    derived_path = root / "data/derived/sc1-site.json"
    generated_path = root / "site/src/generated/sc1-site.json"
    if not audit_path.is_file():
        return [f"missing audit artifact: {audit_path}"]
    if not dependency_path.is_file():
        return [f"missing dependency artifact: {dependency_path}"]
    try:
        audit = read_json(audit_path)
        dependencies = read_json(dependency_path)
    except (OSError, ValueError) as exc:
        return [f"cannot read D1.0 artifact: {exc}"]

    if not isinstance(audit, dict) or audit.get("audit") != "D1.0":
        errors.append("bundle audit has an invalid audit marker")
    if not isinstance(dependencies, dict) or dependencies.get("schema") != 1:
        errors.append("dependency audit has an invalid schema marker")

    if derived_path.read_bytes() != generated_path.read_bytes():
        errors.append("SC1 derived and generated JSON files are no longer byte-identical")
    current_derived_sha = sha256_file(derived_path)
    current_generated_sha = sha256_file(generated_path)
    inputs = audit.get("inputs", {}) if isinstance(audit, dict) else {}
    current_bundle = read_json(derived_path)
    d1_1_shape = (
        isinstance(current_bundle, dict)
        and isinstance(current_bundle.get("display"), dict)
        and all(
            key not in story.get("reading", {})
            for story in current_bundle.get("stories", [])
            if isinstance(story, dict)
        for key in ("labels", "person_display", "source_display", "relation_display", "evidence_display")
        )
    )
    if inputs.get("derived_sha256") != current_derived_sha and not d1_1_shape:
        errors.append("recorded derived SC1 SHA256 does not match the current file")
    if inputs.get("generated_sha256") != current_generated_sha and not d1_1_shape:
        errors.append("recorded generated SC1 SHA256 does not match the current file")
    if inputs.get("byte_identical") is not True:
        errors.append("audit did not record byte identity")
    if inputs.get("required_top_level_fields") != REQUIRED_TOP_LEVEL_FIELDS:
        errors.append("required top-level field manifest is incomplete or reordered")

    if d1_1_shape:
        # D1.0 remains a frozen measurement of the pre-deduplication bundle.
        # Validate that historical input from the recorded Git revision still
        # matches the audit, while allowing the intentional D1.1 projection to
        # replace the current working-tree bytes.
        commit = str(audit.get("baseline", {}).get("git_head", ""))
        expected_sha = str(inputs.get("derived_sha256", ""))
        try:
            baseline_payload = subprocess.check_output(
                ["git", "show", f"{commit}:data/derived/sc1-site.json"],
                cwd=root,
            )
            if hashlib.sha256(baseline_payload).hexdigest() != expected_sha:
                errors.append("frozen D1.0 Git input no longer matches its recorded SHA256")
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"cannot verify frozen D1.0 Git input: {exc}")
        size = audit.get("bundle_size", {})
        top_fields = audit.get("top_level_fields", [])
        if isinstance(size, dict) and isinstance(top_fields, list):
            if sum(row.get("serialized_bytes", 0) for row in top_fields) != size.get("top_level_field_serialized_bytes"):
                errors.append("frozen D1.0 top-level byte total is inconsistent")
            if size.get("top_level_field_serialized_bytes", 0) + size.get("top_level_syntax_overhead_bytes", 0) != size.get("compact_serialized_bytes"):
                errors.append("frozen D1.0 compact byte total is inconsistent")
        consumers = dependencies.get("consumers", []) if isinstance(dependencies, dict) else []
        paths = [row.get("path") for row in consumers if isinstance(row, dict)]
        if len(paths) != len(set(paths)) or dependencies.get("duplicate_path_count") != 0:
            errors.append("frozen D1.0 dependency audit contains duplicate paths")
        protection = audit.get("protection_manifest", [])
        for row in protection if isinstance(protection, list) else []:
            path = root / str(row.get("path"))
            if not path.is_file():
                errors.append(f"protected file missing from working tree: {path}")
            elif sha256_file(path) != row.get("sha256"):
                errors.append(f"protected file changed after D1.0 audit: {path}")
        return errors

    try:
        current = build_bundle_audit(root)
        current_dependencies = scan_dependencies(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"cannot recompute D1.0 audit: {exc}")
        return errors
    # Compare all deterministic measurements.  The audit itself is excluded
    # from dependency scanning, so this does not create a self-reference.
    for key in [
        "inputs",
        "bundle_size",
        "top_level_fields",
        "nested_metrics",
        "largest_contributors",
        "duplication_findings",
        "runtime_necessity",
        "git_and_runtime_observations",
        "protection_manifest",
    ]:
        _same(audit.get(key), current.get(key), f"audit.{key}", errors)
    _same(dependencies, current_dependencies, "dependency audit", errors)

    size = audit.get("bundle_size", {})
    top_fields = audit.get("top_level_fields", [])
    if not isinstance(top_fields, list) or [row.get("path") for row in top_fields] != REQUIRED_TOP_LEVEL_FIELDS:
        errors.append("top-level size audit does not cover the required fields in order")
    if isinstance(size, dict) and isinstance(top_fields, list):
        if sum(row.get("serialized_bytes", 0) for row in top_fields) != size.get("top_level_field_serialized_bytes"):
            errors.append("top-level field byte total is inconsistent")
        if size.get("top_level_field_serialized_bytes", 0) + size.get("top_level_syntax_overhead_bytes", 0) != size.get("compact_serialized_bytes"):
            errors.append("compact byte total and syntax overhead are inconsistent")
        if size.get("raw_file_bytes") != derived_path.stat().st_size:
            errors.append("raw file byte total is inconsistent")

    consumers = dependencies.get("consumers", []) if isinstance(dependencies, dict) else []
    paths = [row.get("path") for row in consumers if isinstance(row, dict)]
    if len(paths) != len(set(paths)):
        errors.append("dependency audit contains duplicate consumer paths")
    if dependencies.get("duplicate_path_count") != 0:
        errors.append("dependency audit reports duplicate paths")
    if dependencies.get("direct_literal_bundle_consumer_count", 0) > dependencies.get("consumer_count", 0):
        errors.append("direct monolith consumer count exceeds total consumers")

    protection = audit.get("protection_manifest", [])
    for row in protection if isinstance(protection, list) else []:
        if not row.get("exists"):
            errors.append(f"protected file missing: {row.get('path')}")
            continue
        path = root / str(row.get("path"))
        if not path.is_file():
            errors.append(f"protected file missing from working tree: {path}")
        elif sha256_file(path) != row.get("sha256"):
            errors.append(f"protected file changed after D1.0 audit: {path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("D1.0 audit validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
