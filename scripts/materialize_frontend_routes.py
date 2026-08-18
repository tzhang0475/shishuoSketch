#!/usr/bin/env python3
"""Materialize static shells for clean frontend routes."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
ROUTE_SHELLS = (
    Path("index/index.html"),
    Path("review/irr0/index.html"),
)


def materialize_routes(dist_dir: Path = DIST_DIR) -> tuple[Path, ...]:
    """Copy the generated root shell to each clean route location."""
    root_index = dist_dir / "index.html"
    if not root_index.is_file():
        raise FileNotFoundError(f"required frontend shell is missing: {root_index}")

    content = root_index.read_bytes()
    materialized: list[Path] = []
    for relative_path in ROUTE_SHELLS:
        target = dist_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != content:
            target.write_bytes(content)
        materialized.append(target)
    return tuple(materialized)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=DIST_DIR, help="Vite output directory")
    args = parser.parse_args()
    try:
        materialize_routes(args.dist)
    except OSError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
