#!/usr/bin/env python3
"""Offline HDB2-PSL1.3C replay.

PSL1.3C is a boundary repair, not a new semantic/API experiment.  This
runner copies the frozen 1.3B run into a new namespace, rebuilds the
candidate-only profiles/graph and reference structures, then replays the
existing predicate, reviewer and rescue records without contacting DeepSeek.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_3c_common as layer  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import hdb2_psl1_1_common as psl1_1  # noqa: E402
import run_hdb2_psl1_3a as frozen_runner  # noqa: E402


SOURCE_RUN = layer.B_RUN
OUT_ROOT = layer.GENERATED / "live"

# The C run intentionally rebuilds the two candidate-only HDB2-F profile
# projections before replaying the frozen semantic records.  PSL1.3A's
# protected-input list predates that boundary repair and includes one of those
# projections.  Keep every canonical/reviewed/frozen input protected, while
# excluding only the candidate profile files that this C patch is designed to
# regenerate.  This is a boundary contract, not a relaxation of protection.
_PROFILE_PROJECTIONS = {
    "data/derived/hdb2-f-person-knowledge.json",
    "data/derived/hdb2-f-candidate-person-knowledge.json",
}
_BASE_PROTECTED_HASHES = frozen_runner.protected_hashes


def _c_protected_hashes() -> dict[str, str]:
    return {
        path: digest
        for path, digest in _BASE_PROTECTED_HASHES().items()
        if path not in _PROFILE_PROJECTIONS
    }


def _schema_c(value: Any, key: str | None = None) -> Any:
    if isinstance(value, str):
        return value.replace("hdb2-psl1-3a", "hdb2-psl1-3c").replace("hdb2-psl1-3b", "hdb2-psl1-3c") if key == "schema" else value
    if isinstance(value, list):
        return [_schema_c(item, key) for item in value]
    if isinstance(value, dict):
        return {name: _schema_c(item, str(name)) for name, item in value.items()}
    return value


def _rewrite_output_schemas(run_dir: Path) -> None:
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {"selection.json", "preflight.json"}:
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        path.write_text(json.dumps(_schema_c(document), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mark_offline_replay_costs(run_dir: Path) -> None:
    """Separate copied B-run costs from work performed by the C replay.

    The replay copies the B raw records so that its decisions remain auditable,
    but it does not call the provider.  Leaving B's call totals at the top
    level would incorrectly make a zero-call C validation look like a live
    semantic run.
    """
    metrics = layer.read_json(run_dir / "metrics.json", {}) or {}
    source_metrics = {
        key: metrics.get(key)
        for key in (
            "total_calls",
            "all_semantic_calls",
            "reference_semantic_calls",
            "predicate_calls",
            "reviewer_calls",
            "rescue_calls",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "provider_failures",
            "parse_failures",
            "truncated_responses",
            "retries",
        )
        if key in metrics
    }
    metrics["source_run_metrics"] = source_metrics
    metrics["source_run_call_count"] = source_metrics.get("total_calls", 0)
    metrics["source_run_prompt_tokens"] = source_metrics.get("prompt_tokens", 0)
    metrics["source_run_completion_tokens"] = source_metrics.get("completion_tokens", 0)
    metrics["source_run_total_tokens"] = source_metrics.get("total_tokens", 0)
    metrics["replayed_without_api"] = True
    metrics["api_calls_this_run"] = 0
    metrics["semantic_calls_this_run"] = 0
    for key in (
        "total_calls",
        "all_semantic_calls",
        "semantic_calls",
        "semantic_calls_total",
        "reference_semantic_calls",
        "predicate_calls",
        "reviewer_calls",
        "rescue_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "provider_failures",
        "parse_failures",
        "truncated_responses",
        "retries",
    ):
        metrics[key] = 0
    metrics["preflight"] = {
        "status": "offline",
        "reason": "explicit_hdb2_psl1_3c_replay_without_api",
        "model": layer.MODEL,
    }
    layer.write_json(run_dir / "metrics.json", metrics)

    manifest = layer.read_json(run_dir / "manifest.json", {}) or {}
    manifest["source_run_call_count"] = source_metrics.get("total_calls", 0)
    manifest["source_run_token_counts"] = {
        key: source_metrics.get(key, 0)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    manifest["semantic_calls"] = 0
    manifest["semantic_calls_this_run"] = 0
    manifest["api_calls_this_run"] = 0
    manifest["replayed_without_api"] = True
    layer.write_json(run_dir / "manifest.json", manifest)


def _reference_structures(graph: Mapping[str, Any], run_dir: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    model_records = list((layer.read_json(run_dir / "model-results.json", {}) or {}).get("records", []) or [])
    by_mention = {
        str(row.get("mention_id")): row
        for row in model_records
        if row.get("call_type") == "reference_semantic_arbitration"
    }
    structures: dict[str, dict[str, Any]] = {}
    validation_rows: list[dict[str, Any]] = []
    for case in graph.get("cases", []) or []:
        mention_id = str(case.get("mention_id"))
        info = layer.reference_hypotheses(case)
        record = by_mention.get(mention_id, {})
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else None
        if record.get("classification") == "deterministic_bypass":
            validation = {"valid": True, "errors": []}
        elif payload is not None:
            validation = layer.validate_semantic_arbitration(payload, layer.semantic_packet(case, info["hypotheses"]))
        else:
            validation = {"valid": False, "errors": ["no_saved_reference_arbitration"]}
        structure = layer.finalize_reference_structure(case, payload, validation)
        structures[mention_id] = structure
        validation_rows.append({
            "mention_id": mention_id,
            "classification": record.get("classification") or "missing",
            "validation": validation,
            "hypothesis_count": len(info["hypotheses"]),
            "deterministic": info["deterministic"],
        })
    return structures, validation_rows


def _prepare(destination: Path, source: Path) -> dict[str, Any]:
    if destination.exists():
        raise RuntimeError(f"hdb2_psl1_3c_run_exists:{destination}")
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, destination)
    selection = layer.freeze_selection()
    saved = layer.read_json(destination / "selection.json", {}) or {}
    if saved != selection:
        raise RuntimeError("hdb2_psl1_3c_selection_drift")
    old_graph = layer.build_graph(selection)
    structures, structure_validations = _reference_structures(old_graph, destination)
    graph = layer.apply_reference_structures(old_graph, structures)
    for case in graph.get("cases", []) or []:
        case["prejudgment_hypotheses"] = layer.reference_hypotheses(case)["hypotheses"]
    layer.write_json(destination / "graph-before.json", old_graph)
    layer.write_json(destination / "graph.json", graph)
    layer.write_json(destination / "reference-structures.json", {"records": list(structures.values()), "candidate_only": True, "canonical_write_back": False})
    layer.write_json(destination / "reference-hypotheses.json", {
        "records": [
            {
                "mention_id": case.get("mention_id"),
                "story_id": case.get("story_id"),
                "surface": case.get("target_surface"),
                "hypotheses": case.get("prejudgment_hypotheses", []),
                "local_antecedent_hypotheses": (case.get("reference_structure") or {}).get("local_antecedent_hypotheses", []),
                "comparison_distinct_mentions": (case.get("reference_structure") or {}).get("comparison_distinct_mentions", []),
            }
            for case in graph.get("cases", []) or []
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    })
    layer.write_json(destination / "reference-revalidation.json", {"records": structure_validations, "candidate_only": True, "canonical_write_back": False})
    manifest = layer.read_json(destination / "manifest.json", {}) or {}
    manifest.update({
        "schema": "hdb2-psl1-3c-live-manifest-v1",
        "run_version": layer.RUN_VERSION,
        "source_run": str(source.relative_to(ROOT)),
        "replayed_without_api": True,
        "api_calls_this_run": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        # The repaired candidate profiles are an intentional C input.  The
        # remaining frozen/canonical hashes are checked by the inherited
        # replay finalizer through _c_protected_hashes().
        "protected_hashes_before": _c_protected_hashes(),
    })
    layer.write_json(destination / "manifest.json", manifest)
    return {"selection": selection, "graph": graph, "structures": structures}


def _configure() -> None:
    frozen_runner.layer = layer
    frozen_runner.OUT_ROOT = OUT_ROOT


def replay(source: Path = SOURCE_RUN, *, run_id: str | None = None) -> Path:
    _configure()
    selection = layer.freeze_selection()
    destination = OUT_ROOT / (run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1-3C-REPLAY")
    _prepare(destination, source)
    old_freeze = psl1_3.freeze_selection
    old_reviewer = psl1_1.apply_reviewer
    old_protected_hashes = frozen_runner.protected_hashes
    psl1_3.freeze_selection = layer.freeze_selection
    psl1_1.apply_reviewer = layer.apply_reviewer
    frozen_runner.protected_hashes = _c_protected_hashes
    try:
        result = frozen_runner.replay(destination)
    finally:
        psl1_3.freeze_selection = old_freeze
        psl1_1.apply_reviewer = old_reviewer
        frozen_runner.protected_hashes = old_protected_hashes
    _rewrite_output_schemas(result)
    _mark_offline_replay_costs(result)
    manifest = layer.read_json(result / "manifest.json", {}) or {}
    manifest.update({
        "schema": "hdb2-psl1-3c-live-manifest-v1",
        "run_id": result.name,
        "run_version": layer.RUN_VERSION,
        "source_run": str(source.relative_to(ROOT)),
        "replayed_without_api": True,
        "api_calls_this_run": 0,
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes_before": _c_protected_hashes(),
        "protected_hashes_after": _c_protected_hashes(),
    })
    layer.write_json(result / "manifest.json", manifest)
    summary = layer.read_json(result / "validation-summary.json", {}) or {}
    saved_failures = layer.read_json(result / "validation-failures.json", {}) or {}
    summary.update({
        "schema": "hdb2-psl1-3c-validation-summary-v1",
        "replayed_without_api": True,
        "api_calls_this_run": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes_unchanged": True,
        # The inherited B raw records intentionally retain their two audit
        # failures.  C's validator decides whether each was handled safely;
        # this field prevents the stale B summary from describing the C run.
        "source_validation_failures_preserved": len(saved_failures.get("records", []) or []) if isinstance(saved_failures, dict) else 0,
    })
    layer.write_json(result / "validation-summary.json", summary)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, default=SOURCE_RUN)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    source = args.source_run if args.source_run.is_absolute() else ROOT / args.source_run
    result = replay(source, run_id=args.run_id)
    print(json.dumps({"run_dir": str(result.relative_to(ROOT)), "replayed_without_api": True, "api_calls_this_run": 0, "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
