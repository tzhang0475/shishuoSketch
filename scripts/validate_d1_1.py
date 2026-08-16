#!/usr/bin/env python3
"""Validate the D1.1 shared-display migration without changing data.

The D1.0 bundle is loaded from its frozen Git revision and normalized into the
new logical shape.  This lets the validator compare reader-visible semantics
while allowing the physical JSON representation to change.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DERIVED_PATH = ROOT / "data/derived/sc1-site.json"
GENERATED_PATH = ROOT / "site/src/generated/sc1-site.json"
D10_AUDIT_PATH = ROOT / "data/derived/d1-0-bundle-size-audit.json"

DISPLAY_TABLES = {
    "labels": "labels",
    "people": "person_display",
    "relations": "relation_display",
    "sources": "source_display",
    "evidence": "evidence_display",
}


def read_json_bytes(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_frozen_d10_bundle(root: Path) -> tuple[dict[str, Any], str]:
    audit = read_json(root / D10_AUDIT_PATH.relative_to(ROOT))
    commit = str(audit.get("baseline", {}).get("git_head", ""))
    expected_sha = str(audit.get("inputs", {}).get("derived_sha256", ""))
    if not commit or not expected_sha:
        raise ValueError("D1.0 audit does not identify its frozen SC1 input")
    try:
        payload = subprocess.check_output(
            ["git", "show", f"{commit}:data/derived/sc1-site.json"],
            cwd=root,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"cannot load frozen D1.0 SC1 bundle: {exc}") from exc
    if sha256_bytes(payload) != expected_sha:
        raise ValueError("frozen D1.0 SC1 bundle hash does not match its audit")
    bundle = read_json_bytes(payload)
    if not isinstance(bundle, dict):
        raise ValueError("frozen D1.0 SC1 bundle is not an object")
    return bundle, commit


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


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        current = read_json(root / DERIVED_PATH.relative_to(ROOT))
        generated = read_json(root / GENERATED_PATH.relative_to(ROOT))
        current_bytes = (root / DERIVED_PATH.relative_to(ROOT)).read_bytes()
        generated_bytes = (root / GENERATED_PATH.relative_to(ROOT)).read_bytes()
        baseline, baseline_commit = load_frozen_d10_bundle(root)
        d10_audit = read_json(root / D10_AUDIT_PATH.relative_to(ROOT))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot read D1.1 validation inputs: {exc}"]

    if current_bytes != generated_bytes or current != generated:
        errors.append("SC1 derived and generated bundle views are not byte/JSON identical")
    if not isinstance(current, dict):
        return ["current SC1 bundle is not an object"]
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

    if logical_core(current) != logical_core(baseline):
        errors.append(
            "logical reader projection differs from frozen D1.0 bundle "
            f"({baseline_commit})"
        )
    baseline_tables: dict[str, dict[str, Any]] = {table: {} for table in DISPLAY_TABLES}
    for story in baseline.get("stories", []):
        reading = story.get("reading", {}) if isinstance(story, dict) else {}
        for table, old_field in DISPLAY_TABLES.items():
            for key, value in reading.get(old_field, {}).items():
                if key in baseline_tables[table] and baseline_tables[table][key] != value:
                    errors.append(f"frozen D1.0 display values conflict: {old_field}/{key}")
                baseline_tables[table].setdefault(key, value)
    if isinstance(shared, dict):
        for table, expected in baseline_tables.items():
            current_table = shared.get(table, {})
            for key, value in expected.items():
                if current_table.get(key) != value:
                    errors.append(f"shared display value differs from D1.0: {table}/{key}")
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
