#!/usr/bin/env python3
"""Replay stable F1 compact outputs without making provider calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f1.common import OUT, read_json, write_json  # noqa: E402


STABLE_OUTPUTS = (
    "architecture-verification.json",
    "selection-verification.json",
    "preflight-validation.json",
    "identity-results.json",
    "occurrence-primary-results.json",
    "boundary-results.json",
    "candidate-semantic-records.json",
    "review-queue.json",
    "semantic-distribution.json",
    "phase-state.json",
    "resume-validation.json",
    "safety-audit.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in STABLE_OUTPUTS:
        source = OUT / name
        if not source.is_file():
            continue
        value = read_json(source)
        target = destination / name
        write_json(target, value)
        copied[name] = _sha256(target)
    result = {
        "schema": "sfh2-f1-offline-replay-v1",
        "provider_calls": 0,
        "source_namespace": str(OUT.relative_to(ROOT)),
        "destination": str(destination),
        "stable_output_hashes": copied,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(destination / "replay-manifest.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="disposable replay destination")
    args = parser.parse_args(argv)
    print(json.dumps(replay(args.output.resolve()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
