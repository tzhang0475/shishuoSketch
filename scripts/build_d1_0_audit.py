#!/usr/bin/env python3
"""Build the deterministic D1.0 SC1 runtime-bundle audit."""

from __future__ import annotations

from pathlib import Path

try:
    from .d1_0_common import (
        AUDIT_PATH,
        DEPENDENCY_PATH,
        build_bundle_audit,
        scan_dependencies,
        write_json,
    )
except ImportError:  # direct execution from the repository root
    from d1_0_common import AUDIT_PATH, DEPENDENCY_PATH, build_bundle_audit, scan_dependencies, write_json


def main() -> int:
    audit = build_bundle_audit()
    dependencies = scan_dependencies()
    write_json(AUDIT_PATH, audit)
    write_json(DEPENDENCY_PATH, dependencies)
    size = audit["bundle_size"]
    print(
        "D1.0 audit built: "
        f"{size['raw_file_bytes']} raw bytes, "
        f"{audit['inputs']['derived_sha256'][:16]}…; "
        f"{dependencies['consumer_count']} dependency consumers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

