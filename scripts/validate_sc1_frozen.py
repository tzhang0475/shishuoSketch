#!/usr/bin/env python3
"""Verify the immutable FROZEN_SC1_V1 integrity contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from .sc1_paths import (
        FROZEN_SC1_DERIVED_PATH,
        FROZEN_SC1_BYTE_SIZE,
        FROZEN_SC1_MANIFEST_PATH,
        FROZEN_SC1_SHA256,
        FROZEN_SC1_VITE_PATH,
    )
except ImportError:  # direct script execution
    from sc1_paths import (
        FROZEN_SC1_DERIVED_PATH,
        FROZEN_SC1_BYTE_SIZE,
        FROZEN_SC1_MANIFEST_PATH,
        FROZEN_SC1_SHA256,
        FROZEN_SC1_VITE_PATH,
    )


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / FROZEN_SC1_MANIFEST_PATH
    derived_path = root / FROZEN_SC1_DERIVED_PATH
    vite_path = root / FROZEN_SC1_VITE_PATH
    schema_path = root / "schema/sc1-site.schema.json"
    try:
        manifest = read_json(manifest_path)
        bundle = read_json(derived_path)
        read_json(vite_path)
        schema = read_json(schema_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"FROZEN_SC1_V1 cannot read integrity inputs: {exc}"]

    expected = {
        "schema": "frozen-sc1-v1-manifest",
        "logical_name": "FROZEN_SC1_V1",
        "artifact_path": FROZEN_SC1_DERIVED_PATH.as_posix(),
        "frontend_artifact_path": FROZEN_SC1_VITE_PATH.as_posix(),
        "sha256": FROZEN_SC1_SHA256,
        "frontend_sha256": FROZEN_SC1_SHA256,
        "byte_size": FROZEN_SC1_BYTE_SIZE,
        "frontend_byte_size": FROZEN_SC1_BYTE_SIZE,
        "current_status": "frozen",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(f"frozen manifest {key} is not stable: {manifest.get(key)!r} != {value!r}")
    if sha256_file(derived_path) != FROZEN_SC1_SHA256:
        errors.append("FROZEN_SC1_V1 derived SHA256 changed")
    if sha256_file(vite_path) != FROZEN_SC1_SHA256:
        errors.append("FROZEN_SC1_V1 Vite SHA256 changed")
    if derived_path.read_bytes() != vite_path.read_bytes():
        errors.append("FROZEN_SC1_V1 derived and Vite views differ")
    if derived_path.stat().st_size != FROZEN_SC1_BYTE_SIZE or vite_path.stat().st_size != FROZEN_SC1_BYTE_SIZE:
        errors.append("FROZEN_SC1_V1 byte size changed")
    try:
        Draft202012Validator.check_schema(schema)
        errors.extend(
            f"FROZEN_SC1_V1 schema: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(bundle)
        )
    except (ValueError, TypeError) as exc:
        errors.append(f"FROZEN_SC1_V1 schema cannot be validated: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate()
    if errors:
        print("FROZEN_SC1_V1 validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("FROZEN_SC1_V1 integrity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
