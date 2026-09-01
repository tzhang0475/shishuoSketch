#!/usr/bin/env python3
"""Run one repository test contract from the C1 classification registry.

The registry is the source of truth for suite membership.  This runner keeps
the current, historical, source-payload, and live-network contracts separate
without moving the existing test modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = ROOT / "data/derived/test-suite-classification-c1.json"

MODE_TO_CLASSIFICATION = {
    "current": "CURRENT_REQUIRED",
    "historical": "HISTORICAL_REPRODUCIBILITY",
    "source": "SOURCE_PAYLOAD_OPTIONAL",
    "network": "LIVE_NETWORK_EXPERIMENT",
}


def load_classification(path: Path = CLASSIFICATION_PATH) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping) or not isinstance(document.get("tests"), list):
        raise ValueError(f"invalid test classification registry: {path}")
    return document


def selected_test_paths(document: Mapping[str, Any], classification: str) -> list[str]:
    selected: list[str] = []
    for row in document["tests"]:
        if not isinstance(row, Mapping):
            raise ValueError("test classification rows must be objects")
        path = row.get("path")
        if not isinstance(path, str) or not path.startswith("tests/") or not path.endswith(".py"):
            raise ValueError(f"invalid test path in classification: {path!r}")
        if row.get("classification") == classification:
            if not (ROOT / path).is_file():
                raise ValueError(f"classified test is missing: {path}")
            selected.append(path)
    return sorted(set(selected))


def module_name(path: str) -> str:
    return path[:-3].replace("/", ".")


def run_suite(mode: str, *, classification_path: Path = CLASSIFICATION_PATH) -> int:
    classification = MODE_TO_CLASSIFICATION[mode]
    document = load_classification(classification_path)
    paths = selected_test_paths(document, classification)
    print(f"test contract: {mode} ({classification}); modules={len(paths)}")
    if not paths:
        print("no tests are registered for this contract")
        return 0
    command = [sys.executable, "-m", "unittest", *[module_name(path) for path in paths]]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=sorted(MODE_TO_CLASSIFICATION))
    parser.add_argument("--list", action="store_true", help="list selected test modules without running them")
    args = parser.parse_args(argv)
    classification = MODE_TO_CLASSIFICATION[args.mode]
    document = load_classification()
    paths = selected_test_paths(document, classification)
    if args.list:
        print("\n".join(paths))
        return 0
    return run_suite(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
