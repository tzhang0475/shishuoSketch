#!/usr/bin/env python3
"""Validate the offline SFH2.2-A2GR Gold promotion and identity freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/sfh2-a2gr"
FREEZE_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
AUTHORITY_PATH = ROOT / "data/annotation/sfh2-a2gr-human-semantic-authority.json"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
BASELINE_COMMIT = "c57bf17ff2ca783b98d492e412114edf5dd776b0"
SELECTION_HASH = "b8162d9d470c6359c67a8ed31aa31ef82149c12d92dd9a694b62327fc204bbc3"
OLD_GOLD_SHA256 = "82f36497b632032bc164c09fd5db97e35e20c256fc9654ac0d2c9b4c704b0b93"
REQUIRED_OUTPUTS = (
    "reviewed-gold-delta.json",
    "identity-re-evaluation.json",
    "identity-qualification.json",
    "metrics.json",
    "recommendation.json",
    "protected-hash-snapshot.json",
)
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def _rows(document: Mapping[str, Any], key: str = "records") -> list[Mapping[str, Any]]:
    value = document.get(key, [])
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _baseline_gold() -> Mapping[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:data/annotation/sfh2-a0-evaluation-gold.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _tree_snapshot(path: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                files.append({
                    "path": str(child.relative_to(ROOT)),
                    "sha256": file_hash(child),
                    "size_bytes": child.stat().st_size,
                })
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "path": str(path.relative_to(ROOT)),
        "file_count": len(files),
        "total_bytes": sum(row["size_bytes"] for row in files),
        "tree_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": files,
    }


def _provider_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "provider_calls" and isinstance(child, (int, float)) and child != 0:
                errors.append(f"provider_calls_nonzero:{child_path}")
            errors.extend(_provider_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_provider_errors(child, f"{path}[{index}]"))
    return errors


def _deep_diff(before: Any, after: Any, path: str = "") -> list[str]:
    if type(before) is not type(after):
        return [path or "$" ]
    if isinstance(before, Mapping):
        result: list[str] = []
        for key in sorted(set(before) | set(after), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(_deep_diff(before[key], after[key], child))
        return result
    if isinstance(before, list):
        result: list[str] = []
        for index in range(max(len(before), len(after))):
            child = f"{path}[{index}]"
            if index >= len(before) or index >= len(after):
                result.append(child)
            else:
                result.extend(_deep_diff(before[index], after[index], child))
        return result
    return [] if before == after else [path or "$" ]


def validate() -> dict[str, Any]:
    errors: list[str] = []
    gold = load_json(GOLD_PATH, {}) or {}
    authority = load_json(AUTHORITY_PATH, {}) or {}
    selection = load_json(SELECTION_PATH, {}) or {}
    baseline_gold = _baseline_gold()
    outputs = {name: load_json(OUT / name, {}) or {} for name in REQUIRED_OUTPUTS}

    if not (ROOT / ".git").exists():
        errors.append("git_metadata_missing")
    if selection.get("selection_hash") != SELECTION_HASH or len(_rows(selection, "cases")) != 20:
        errors.append("selection_not_frozen")
    if text(gold.get("schema")) != "sfh2-a0-evaluation-gold-v3":
        errors.append("reviewed_gold_schema_missing")
    if gold.get("evaluation_only") is not True or gold.get("not_for_provider") is not True:
        errors.append("gold_evaluation_boundary_missing")
    if gold.get("revision", {}).get("previous_sha256") != OLD_GOLD_SHA256:
        errors.append("gold_predecessor_hash_missing")

    authority_rows = _rows(authority)
    if text(authority.get("schema")) != "sfh2-a2gr-human-semantic-authority-v1":
        errors.append("authority_schema_missing")
    if len(authority_rows) != 4 or any(row.get("review_status") != "reviewed" for row in authority_rows):
        errors.append("authority_not_four_reviewed_records")
    if authority.get("candidate_only") is not False or authority.get("canonical_write_back") is not False:
        errors.append("authority_storage_boundary_missing")
    baseline_map = {text(row.get("case_key")): row for row in _rows(baseline_gold)}
    active_map = {text(row.get("case_key")): row for row in _rows(gold)}
    authority_changed = []
    authority_reaffirmed = []
    for row in authority_rows:
        key = text(row.get("case_key"))
        if row.get("candidate_only") is not False or row.get("canonical_write_back") is not False:
            errors.append(f"authority_record_storage:{key}")
        if row.get("previous_gold") != baseline_map.get(key):
            errors.append(f"authority_previous_gold_mismatch:{key}")
        if row.get("reviewed_gold") != active_map.get(key):
            errors.append(f"authority_reviewed_gold_mismatch:{key}")
        if row.get("decision") == "revise_gold":
            authority_changed.append(key)
        elif row.get("decision") == "reaffirm_gold":
            authority_reaffirmed.append(key)
        else:
            errors.append(f"authority_decision_invalid:{key}")
    if len(authority_changed) != 1 or len(authority_reaffirmed) != 3:
        errors.append("authority_promotion_cardinality")

    delta = outputs["reviewed-gold-delta.json"]
    if delta.get("source_gold_sha256") != OLD_GOLD_SHA256 or delta.get("reviewed_gold_sha256") != file_hash(GOLD_PATH):
        errors.append("gold_delta_hashes")
    changed = delta.get("changed_cases", [])
    if delta.get("substantive_mutation_count") != 1 or len(changed) != 1:
        errors.append("gold_delta_not_one_substantive_mutation")
    if changed and changed[0].get("before") != baseline_map.get(changed[0].get("case_key")):
        errors.append("gold_delta_before_not_predecessor")
    if changed and changed[0].get("after") != active_map.get(changed[0].get("case_key")):
        errors.append("gold_delta_after_not_active")
    if sorted(delta.get("reaffirmed_cases", [])) != sorted(authority_reaffirmed):
        errors.append("gold_reaffirmation_set")

    evaluation = outputs["identity-re-evaluation.json"]
    eval_rows = _rows(evaluation)
    if len(eval_rows) != 20:
        errors.append("identity_evaluation_not_20")
    if evaluation.get("identity_evaluable_before") != 18 or evaluation.get("identity_evaluable_after") != 17:
        errors.append("identity_evaluable_counts")
    after = evaluation.get("after", {})
    final_identity = after.get("final_identity", {})
    if final_identity.get("correct") != 17 or final_identity.get("wrong") != 0 or final_identity.get("unresolved") != 0:
        errors.append("final_identity_gate_metrics")

    qualification = outputs["identity-qualification.json"]
    if qualification.get("identity_pipeline_status") != "qualified_and_frozen" or qualification.get("gate_passed") is not True:
        errors.append("identity_qualification_not_passed")
    if any(value is not True for value in (qualification.get("checks") or {}).values()):
        errors.append("identity_qualification_check_failed")
    if outputs["recommendation.json"].get("recommendation") != "sfh2_identity_pipeline_frozen":
        errors.append("recommendation_not_frozen")
    if outputs["recommendation.json"].get("next_stage") != "SFH2.2-A2O":
        errors.append("next_stage_not_a2o")

    freeze = load_json(FREEZE_PATH, {}) or {}
    if not freeze:
        errors.append("identity_freeze_manifest_missing")
    if freeze.get("baseline_commit") != BASELINE_COMMIT:
        errors.append("freeze_baseline_mismatch")
    if freeze.get("reviewed_gold_sha256") != file_hash(GOLD_PATH):
        errors.append("freeze_gold_hash_mismatch")
    if freeze.get("identity_pipeline_status") != "qualified_and_frozen":
        errors.append("freeze_status_missing")
    if freeze.get("a2gr_commit_placeholder") != "pending-final-commit":
        errors.append("freeze_commit_placeholder_missing")
    if freeze.get("provider_calls") != 0:
        errors.append("freeze_provider_boundary")

    protected_paths = {
        "data/derived/sc1-site.json": FROZEN_SC1_SHA256,
        "data/derived/sc1-current-site.json": CURRENT_SC1_SHA256,
        "site/src/generated/sc1-site.json": FROZEN_SC1_SHA256,
        "site/src/generated/sc1-current-site.json": CURRENT_SC1_SHA256,
    }
    for relative, expected in protected_paths.items():
        path = ROOT / relative
        if not path.is_file() or file_hash(path) != expected:
            errors.append(f"protected_sc1_hash:{relative}")
    for relative, expected in (freeze.get("protected_file_hashes") or {}).items():
        path = ROOT / relative
        if not path.is_file() or file_hash(path) != expected:
            errors.append(f"protected_file_changed:{relative}")

    for relative, snapshot in (freeze.get("protected_experiment_trees") or {}).items():
        current = _tree_snapshot(ROOT / relative)
        if current.get("tree_sha256") != snapshot.get("tree_sha256") or current.get("file_count") != snapshot.get("file_count"):
            errors.append(f"protected_tree_changed:{relative}")

    snapshot = outputs["protected-hash-snapshot.json"]
    if snapshot.get("trees") != freeze.get("protected_experiment_trees"):
        errors.append("protected_snapshot_mismatch")
    if snapshot.get("files") != freeze.get("protected_file_hashes"):
        errors.append("protected_file_snapshot_mismatch")

    for name, document in outputs.items():
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"storage_boundary:{name}")
        errors.extend(f"{name}:{error}" for error in _provider_errors(document))
    errors.extend(f"freeze-manifest:{error}" for error in _provider_errors(freeze))

    # The promoted Gold must agree with the evaluation-only builder.  This is
    # a contract check, not a runtime identity rule.
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from sfh2_a0.selection import build_evaluation_gold
        if build_evaluation_gold() != gold:
            errors.append("gold_builder_drift")
    except Exception as exc:
        errors.append(f"gold_builder_unavailable:{type(exc).__name__}")

    # Keep the A2GR runtime path free of provider clients and surface-specific
    # semantic branches.  Human-reviewed labels live in the authority/Gold
    # inputs, not in executable semantic logic.
    runtime = ROOT / "scripts/run_sfh2_a2gr.py"
    source = runtime.read_text(encoding="utf-8") if runtime.is_file() else ""
    for forbidden in ("requests", "urllib", "httpx", "openai", "DEEPSEEK_API_KEY"):
        if forbidden in source:
            errors.append(f"runtime_provider_dependency:{forbidden}")
    for pattern in (r"surface\s*==", r"surface\s+in\s+", r"case_key\s*=="):
        if re.search(pattern, source):
            errors.append(f"runtime_surface_semantic_rule:{pattern}")
    if "replacement_identity" in source:
        errors.append("runtime_replacement_identity_marker")

    return {
        "schema": "sfh2-a2gr-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "selection_hash": SELECTION_HASH,
        "provider_calls": 0,
        "identity_pipeline_status": qualification.get("identity_pipeline_status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
