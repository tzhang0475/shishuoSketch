#!/usr/bin/env python3
"""Validate HNG2-L generated projections without making API calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hng0_1_common import sha256_file  # noqa: E402
from historical_entity_resolver import RESOLVER_VERSION, person_catalog  # noqa: E402

OUT = ROOT / "data/generated/hng2-live"
SELECTION = OUT / "live-selection.json"
REQUIRED = (
    "live-selection.json", "wave-1-results.json", "wave-2-selection.json", "wave-2-results.json",
    "retrieval-trace.json", "temporal-gate-decisions.json", "rejected-passages.json",
    "identity-deterministic.json", "identity-llm-assist.json", "identity-final.json",
    "identity-graph-support.json", "relations.json", "temporal-items.json", "provisional-persons.json",
    "consolidation-candidates.json", "audit-sample.json", "metrics.json", "manifest.json",
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _quote_ok(source: str, quote: str) -> bool:
    if quote in source:
        return True
    trimmed = quote.strip(" \t\n\r，。；、：:!?！？『』「」（）()[]【】\"")
    return bool(trimmed and trimmed in source)


def validate(*, mode: str = "portable") -> list[str]:
    errors: list[str] = []
    if not SELECTION.is_file():
        return ["missing:live-selection.json"]
    try:
        selection = read(SELECTION)
    except Exception as exc:
        return [f"selection_read:{type(exc).__name__}:{exc}"]
    if selection.get("canonical_write_back") is not False:
        errors.append("selection_canonical_write_back")
    people = selection.get("people", [])
    if selection.get("selected_count") != 24 or len(people) != 24:
        errors.append("selection_count_not_24")
    ids = [str(row.get("frontier_id") or "") for row in people]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        errors.append("selection_duplicate_or_empty_frontier")
    if not selection.get("frozen"):
        errors.append("selection_not_frozen")
    if selection.get("wave_cap") != 2 or selection.get("one_hop_only") is not True:
        errors.append("selection_wave_boundary")
    for rel, expected in (selection.get("source_hashes") or {}).items():
        path = ROOT / str(rel)
        if not path.is_file():
            errors.append(f"missing_frozen_baseline:{rel}")
        elif sha256_file(path) != str(expected):
            errors.append(f"frozen_baseline_changed:{rel}")
    if mode == "portable":
        # Portable validation is deliberately usable immediately after the
        # environment preflight abort, before story result files exist.
        status_path = OUT / "run-status.json"
        if status_path.is_file() and read(status_path).get("execution_status") == "live_network_unavailable":
            return errors
    for name in REQUIRED:
        if not (OUT / name).is_file():
            errors.append(f"missing:{name}")
    if errors:
        return errors
    try:
        manifest = read(OUT / "manifest.json")
        wave1 = read(OUT / "wave-1-results.json")
        wave2 = read(OUT / "wave-2-results.json")
        wave2_selection = read(OUT / "wave-2-selection.json")
        traces = read(OUT / "retrieval-trace.json").get("records", [])
        gates = read(OUT / "temporal-gate-decisions.json").get("decisions", [])
        identities = read(OUT / "identity-final.json").get("records", [])
        assist = read(OUT / "identity-llm-assist.json")
        relations = read(OUT / "relations.json").get("relations", [])
        temporal = read(OUT / "temporal-items.json").get("temporal_items", [])
        audit = read(OUT / "audit-sample.json").get("items", [])
        metrics = read(OUT / "metrics.json")
    except Exception as exc:
        return [f"read_error:{type(exc).__name__}:{exc}"]
    if manifest.get("canonical_write_back") is not False:
        errors.append("manifest_canonical_write_back")
    if manifest.get("resolver_version") != RESOLVER_VERSION:
        errors.append("resolver_version_mismatch")
    if manifest.get("wave_cap") != 2 or manifest.get("one_hop_only") is not True:
        errors.append("manifest_wave_boundary")
    if wave2_selection.get("wave_3_created") is True or wave2.get("wave_3_created") is True:
        errors.append("wave3_created")
    if any(int(row.get("wave") or 0) > 2 for row in [*relations, *temporal, *traces, *wave2_selection.get("frontiers", [])]):
        errors.append("third_wave_record")
    if any(row.get("canonical_write_back") is not False for row in [*relations, *temporal, *identities, *audit]):
        errors.append("candidate_canonical_write_back")
    if len(wave1.get("results", [])) > 24:
        errors.append("wave1_over_cap")
    if len(wave2_selection.get("frontiers", [])) > 8 or len(wave2.get("results", [])) > 8:
        errors.append("wave2_over_cap")
    person_ids = set(person_catalog())
    for row in identities:
        resolved = str(row.get("final_person_id") or "")
        if resolved and resolved not in person_ids:
            errors.append(f"identity_unknown_person:{row.get('occurrence_id')}")
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        graph = row.get("graph_support") if isinstance(row.get("graph_support"), Mapping) else {}
        if row.get("final_status") in {"llm_resolved", "deterministic_resolved"} and not row.get("evidence_ref"):
            errors.append(f"identity_without_evidence:{row.get('occurrence_id')}")
        if graph.get("independent_graph_support_count", 0) and row.get("assist_called") and row.get("final_status") == "llm_resolved" and not resolution.get("candidate_set"):
            errors.append(f"llm_graph_only_candidate:{row.get('occurrence_id')}")
    for row in relations:
        if not row.get("evidence_refs") or not row.get("evidence_quotes"):
            errors.append(f"relation_without_evidence:{row.get('relation_id')}")
        if row.get("semantic_level") not in {"hard_relation", "documented_interaction", "interpreted_relation"}:
            errors.append(f"relation_level:{row.get('relation_id')}")
        if row.get("one_hop_only") is not True:
            errors.append(f"relation_not_one_hop:{row.get('relation_id')}")
    for row in temporal:
        if not row.get("evidence_refs") or row.get("one_hop_only") is not True:
            errors.append(f"temporal_evidence_or_hop:{row.get('temporal_id')}")
    trace_ids = {str(row.get("frontier_id")) for row in traces}
    selected_ids = set(ids)
    if not trace_ids.issubset(selected_ids | {str(row.get("frontier_id")) for row in wave2_selection.get("frontiers", [])}):
        errors.append("trace_outside_selection")
    for row in traces:
        if not set(str(x) for x in row.get("used_refs", [])).issubset(set(str(x) for x in row.get("opened_refs", []))):
            errors.append(f"used_ref_not_opened:{row.get('frontier_id')}")
        for gate in row.get("seed_identity_gate_decisions", []):
            if gate.get("temporal", {}).get("status") == "conflict" and str(gate.get("evidence_ref")) not in {str(x.get("evidence_ref")) for x in row.get("rejected_by_temporal_gate", [])}:
                errors.append(f"temporal_conflict_not_rejected:{row.get('frontier_id')}:{gate.get('evidence_ref')}")
    if assist.get("canonical_write_back") is not False:
        errors.append("identity_assist_canonical_write_back")
    if metrics.get("execution_status") != "completed":
        errors.append("metrics_not_completed")
    # Raw API responses are immutable artifacts: every listed path must exist
    # and its contents must not contain the secret name/value.
    for item in manifest.get("raw_extractions", []):
        path = ROOT / str(item.get("path") or "")
        if not path.is_file():
            errors.append(f"missing_raw:{item.get('path')}")
        elif "DEEPSEEK_API_KEY" in path.read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"secret_marker_in_raw:{item.get('path')}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    errors = validate(mode=args.mode)
    if errors:
        print("HNG2-L validation failed:")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print("HNG2-L validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
