#!/usr/bin/env python3
"""Validate SRM0.5 selection, frozen protocol, and live-only projections."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, stable_json  # noqa: E402
import run_srm0_5 as runner  # noqa: E402


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_selection(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = root / runner.SELECTION_PATH
    document = _read(path)
    if not isinstance(document, Mapping):
        return [f"missing or invalid selection: {runner.SELECTION_PATH}"]
    selected = document.get("selected")
    ids = document.get("selected_story_ids")
    if not isinstance(selected, list) or not isinstance(ids, list):
        errors.append("selection selected/selected_story_ids must be arrays")
        return errors
    if len(selected) != 15 or len(ids) != 15 or len(set(ids)) != 15:
        errors.append("selection must contain exactly 15 unique Stories")
    counts = {stratum: sum(row.get("stratum") == stratum for row in selected if isinstance(row, Mapping)) for stratum in runner.STRATA}
    if counts != runner.TARGETS:
        errors.append(f"selection strata counts {counts} != {runner.TARGETS}")
    canonical = set(runner.story_ids_from_corpus(root))
    excluded = set(document.get("excluded_stories") or [])
    if not set(ids).issubset(canonical):
        errors.append("selection contains a non-canonical Story")
    if set(ids) & excluded:
        errors.append("selection contains a Story in its exclusion set")
    if [row.get("story_id") for row in selected if isinstance(row, Mapping)] != ids:
        errors.append("selected_story_ids order does not match selected rows")
    for row in selected:
        if not isinstance(row, Mapping):
            errors.append("selection row is not an object")
            continue
        story_id = str(row.get("story_id"))
        if row.get("deterministic_selection_key") != runner._selection_key(story_id):
            errors.append(f"selection key mismatch: {story_id}")
        if not row.get("exclusion_basis"):
            errors.append(f"missing exclusion basis: {story_id}")
        try:
            material = runner.story_material(root, story_id)
        except Exception as exc:  # pragma: no cover - diagnostic branch
            errors.append(f"cannot load selected Story {story_id}: {exc}")
            continue
        for field in ("main_text_chars", "liu_block_count", "jianshu_chars"):
            if int(row.get(field, -1)) != int(material[field]):
                errors.append(f"selection metric mismatch {story_id}.{field}")
    expected = runner.selection_document(root)
    if expected.get("selected_story_ids") != ids:
        errors.append("selection is not reproducible from the current canonical/source inputs")
    return errors


def validate_protocol(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    selection = _read(root / runner.SELECTION_PATH)
    freeze = _read(root / runner.OUTPUT_ROOT / "protocol-freeze.json")
    if not isinstance(selection, Mapping) or not isinstance(freeze, Mapping):
        return ["selection or protocol-freeze is missing"]
    if freeze.get("prompt_version") != runner.PROMPT_VERSION:
        errors.append("prompt version drift")
    if freeze.get("selection_hash") != runner._hash_value(selection.get("selected_story_ids", [])):
        errors.append("protocol selection hash mismatch")
    current = runner._algorithm_snapshot(root)
    if freeze.get("algorithm_snapshot") != current:
        errors.append("frozen SRM0.4 algorithm snapshot differs from current helper files")
    if freeze.get("canonical_write_back") is not False:
        errors.append("protocol freeze permits canonical write-back")
    return errors


def _validate_story_run(root: Path, row: Mapping[str, Any], protocol: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    story_id = str(row.get("story_id"))
    run_id = str(row.get("run_id"))
    run_dir = root / runner.OUTPUT_ROOT / "live" / story_id / run_id
    if not run_dir.is_dir():
        return [f"missing live run directory: {run_dir}"]
    manifest = _read(run_dir / "manifest.json")
    if not isinstance(manifest, Mapping):
        errors.append(f"live manifest missing: {run_dir}")
    else:
        for name, expected_hash in (manifest.get("artifact_hashes") or {}).items():
            artifact = run_dir / str(name)
            if not artifact.is_file():
                errors.append(f"manifest artifact missing: {artifact}")
            elif _hash(artifact) != expected_hash:
                errors.append(f"immutable artifact hash changed: {artifact}")
    if row.get("execution_kind") != "live_model":
        errors.append(f"live summary row is not live_model: {story_id}")
    for path in sorted(run_dir.glob("round-*-input.json")):
        document = _read(path)
        if not isinstance(document, Mapping) or document.get("execution_kind") != "live_model":
            errors.append(f"fixture/missing execution kind in {path}")
        if isinstance(document, Mapping) and document.get("prompt_version") != runner.PROMPT_VERSION:
            errors.append(f"prompt version drift in {path}")
    for path in sorted(run_dir.glob("round-*-output.json")):
        document = _read(path)
        if not isinstance(document, Mapping):
            errors.append(f"invalid model output: {path}")
            continue
        if document.get("execution_kind") != "live_model":
            errors.append(f"fixture output in live tree: {path}")
        if document.get("canonical_write_back") is not False:
            errors.append(f"canonical write-back in {path}")
    if row.get("canonical_write_back") is not False or row.get("external_search_performed") is not False:
        errors.append(f"unsafe flags in live row: {story_id}")
    qmetrics = row.get("question_metrics") or {}
    if int(qmetrics.get("converged_question_count", 0)) > int(qmetrics.get("evaluable_question_count", 0)):
        errors.append(f"question convergence count exceeds evaluable count: {story_id}")
    if row.get("execution_kind") == "fixture" or "fixture" in str(row.get("run_id", "")):
        errors.append(f"fixture result mixed into live summary: {story_id}")
    return errors


def validate_live(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    summary = _read(root / runner.SUMMARY_PATH)
    selection = _read(root / runner.SELECTION_PATH)
    protocol = _read(root / runner.OUTPUT_ROOT / "protocol-freeze.json")
    if not isinstance(summary, Mapping):
        return [f"live summary missing: {runner.SUMMARY_PATH}"]
    if summary.get("execution_kind") != "live_model":
        errors.append("summary is not marked live_model")
    rows = summary.get("stories")
    if not isinstance(rows, list):
        return ["summary stories is not an array"]
    expected = list(selection.get("selected_story_ids", [])) if isinstance(selection, Mapping) else []
    actual = [row.get("story_id") for row in rows if isinstance(row, Mapping)]
    if actual != expected:
        errors.append("live summary Story order/set differs from frozen selection")
    for row in rows:
        if isinstance(row, Mapping):
            errors.extend(_validate_story_run(root, row, protocol if isinstance(protocol, Mapping) else {}))
    if "fixture" in stable_json(summary).lower():
        errors.append("fixture marker found in live summary")
    metrics = _read(root / runner.METRICS_PATH)
    if not isinstance(metrics, Mapping):
        errors.append("metrics.json missing after live batch")
    return errors


def validate(root: Path = ROOT, mode: str = "portable") -> list[str]:
    errors = validate_selection(root) + validate_protocol(root)
    if mode in {"full", "live"}:
        errors.extend(validate_live(root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full", "live"), default="portable")
    args = parser.parse_args()
    errors = validate(ROOT, args.mode)
    if errors:
        print("SRM0.5 validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"SRM0.5 validation passed ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
