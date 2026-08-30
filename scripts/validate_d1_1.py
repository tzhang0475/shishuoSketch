#!/usr/bin/env python3
"""Validate the D1.1 shared-display migration without changing data.

The frozen D1.0 reader semantics are represented by compact committed
fingerprints. This keeps validation portable in shallow checkouts while
allowing the physical JSON representation to change.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts import sfh2r_contract
except ImportError:  # direct execution from scripts/
    import sfh2r_contract


ROOT = Path(__file__).resolve().parents[1]
DERIVED_PATH = ROOT / "data/derived/sc1-site.json"
GENERATED_PATH = ROOT / "site/src/generated/sc1-site.json"
D10_AUDIT_PATH = ROOT / "data/derived/d1-0-bundle-size-audit.json"
D10_BASELINE_PATH = ROOT / "data/derived/d1-0-semantic-baseline.json"

DISPLAY_TABLES = {
    "labels": "labels",
    "people": "person_display",
    "relations": "relation_display",
    "sources": "source_display",
    "evidence": "evidence_display",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def logical_core(bundle: dict[str, Any]) -> dict[str, Any]:
    """Remove only the physical display placement from a bundle."""

    result = deepcopy(bundle)
    result.pop("display", None)
    for story in result.get("stories", []):
        if not isinstance(story, dict) or not isinstance(story.get("reading"), dict):
            continue
        for field in DISPLAY_TABLES.values():
            story["reading"].pop(field, None)
    return result


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def table_key_sha256(table: dict[str, Any]) -> str:
    return canonical_sha256(sorted(table))


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        current = read_json(root / DERIVED_PATH.relative_to(ROOT))
        generated = read_json(root / GENERATED_PATH.relative_to(ROOT))
        current_bytes = (root / DERIVED_PATH.relative_to(ROOT)).read_bytes()
        generated_bytes = (root / GENERATED_PATH.relative_to(ROOT)).read_bytes()
        baseline = read_json(root / D10_BASELINE_PATH.relative_to(ROOT))
        d10_audit = read_json(root / D10_AUDIT_PATH.relative_to(ROOT))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot read D1.1 validation inputs: {exc}"]

    if current_bytes != generated_bytes or current != generated:
        errors.append("SC1 derived and generated bundle views are not byte/JSON identical")
    if not isinstance(current, dict):
        return ["current SC1 bundle is not an object"]
    if not isinstance(baseline, dict) or baseline.get("schema") != 1:
        errors.append("D1.0 semantic baseline has an invalid schema marker")
    if baseline.get("artifact") != "D1.0 semantic baseline":
        errors.append("D1.0 semantic baseline has an invalid artifact marker")
    baseline_source = baseline.get("source", {}) if isinstance(baseline, dict) else {}
    d10_inputs = d10_audit.get("inputs", {}) if isinstance(d10_audit, dict) else {}
    if isinstance(baseline_source, dict) and isinstance(d10_inputs, dict):
        if baseline_source.get("bundle_sha256") != d10_inputs.get("derived_sha256"):
            errors.append("D1.0 semantic baseline is not anchored to the D1.0 input SHA256")
        if baseline_source.get("bundle_size_bytes") != d10_audit.get("bundle_size", {}).get("raw_file_bytes"):
            errors.append("D1.0 semantic baseline is not anchored to the D1.0 input size")
    shared = current.get("display")
    if not isinstance(shared, dict):
        errors.append("SC1 bundle lacks shared display registry")
    else:
        for table in DISPLAY_TABLES:
            if not isinstance(shared.get(table), dict):
                errors.append(f"shared display table is missing: {table}")
    for story in current.get("stories", []):
        reading = story.get("reading", {}) if isinstance(story, dict) else {}
        for field in DISPLAY_TABLES.values():
            if field in reading:
                errors.append(f"Story {story.get('id')} retains duplicated display map: {field}")

    expected_core = baseline.get("logical_core", {}) if isinstance(baseline, dict) else {}
    if isinstance(expected_core, dict):
        actual_core = logical_core(current)
        if canonical_sha256(actual_core) != expected_core.get("sha256"):
            errors.append("logical reader projection differs from committed D1.0 semantic baseline")
        expected_counts = expected_core.get("record_counts", {})
        if isinstance(expected_counts, dict):
            for field, expected_count in expected_counts.items():
                if expected_count is None:
                    continue
                value = actual_core.get(field)
                actual_count = len(value) if isinstance(value, (list, dict)) else None
                if actual_count != expected_count:
                    errors.append(f"D1.0 logical-core count differs for {field}")
    expected_tables = baseline.get("display_tables", {}) if isinstance(baseline, dict) else {}
    if not isinstance(expected_tables, dict):
        errors.append("D1.0 semantic baseline display_tables is not an object")
        expected_tables = {}
    if isinstance(shared, dict):
        for table in DISPLAY_TABLES:
            current_table = shared.get(table, {})
            expected = expected_tables.get(table, {})
            if not isinstance(current_table, dict) or not isinstance(expected, dict):
                continue
            if len(current_table) != expected.get("record_count"):
                errors.append(f"shared display count differs from D1.0: {table}")
            if canonical_sha256(current_table) != expected.get("sha256"):
                errors.append(f"shared display values differ from D1.0: {table}")
            if table_key_sha256(current_table) != expected.get("keys_sha256"):
                errors.append(f"shared display keys differ from D1.0: {table}")
    if isinstance(shared, dict):
        expected_ids = {
            "people": {item.get("id") for item in current.get("people", [])},
            "relations": {item.get("id") for item in current.get("relations", [])},
            "sources": {item.get("id") for item in current.get("sources", [])},
            "evidence": {item.get("id") for item in current.get("evidence", [])},
        }
        for table, ids in expected_ids.items():
            if set(shared.get(table, {})) != ids:
                errors.append(f"shared display table does not cover current {table} registry")

    protected = d10_audit.get("protection_manifest", []) if isinstance(d10_audit, dict) else []
    for row in protected if isinstance(protected, list) else []:
        path_text = row.get("path")
        expected = row.get("sha256")
        path = root / str(path_text)
        if not path.is_file():
            errors.append(f"protected D1.0 file is missing: {path_text}")
        elif sha256_bytes(path.read_bytes()) != expected:
            if sfh2r_contract.path_hash_is_current_or_authorized(
                str(path_text), str(expected), sha256_bytes(path.read_bytes())
            ):
                continue
            errors.append(f"protected D1.0 file changed: {path_text}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("D1.1 semantic-equivalence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
