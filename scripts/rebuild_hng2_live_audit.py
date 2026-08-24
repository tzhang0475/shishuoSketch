#!/usr/bin/env python3
"""Rebuild only the deterministic HNG2-L audit projection.

This is an offline reporting utility.  It never reads credentials, calls
DeepSeek, or changes raw API artifacts.
"""

from __future__ import annotations

import sys
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from hng0_1_common import write_json  # noqa: E402
from run_hng2_live import OUT, _audit, _write_review, read_json  # noqa: E402


def rebuild() -> dict:
    identities = read_json(OUT / "identity-final.json", {}).get("records", [])
    for row in identities:
        if not row.get("wave"):
            row["wave"] = 2 if "-w2-" in str(row.get("occurrence_id")) else 1
    write_json(OUT / "identity-final.json", {**read_json(OUT / "identity-final.json", {}), "records": identities, "offline_rebuild": True})
    deterministic_path = OUT / "identity-deterministic.json"
    if deterministic_path.is_file():
        deterministic = read_json(deterministic_path, {})
        deterministic_rows = deterministic.get("records", [])
        for row in deterministic_rows:
            if not row.get("wave"):
                row["wave"] = 2 if "-w2-" in str(row.get("occurrence_id")) else 1
        write_json(deterministic_path, {**deterministic, "records": deterministic_rows, "offline_rebuild": True})
    rejected = read_json(OUT / "rejected-passages.json", {}).get("records", [])
    wave2 = read_json(OUT / "wave-2-selection.json", {}).get("frontiers", [])
    consolidations = read_json(OUT / "consolidation-candidates.json", {}).get("candidates", [])
    audit = _audit(identities, [row for row in rejected if "temporal" in str(row.get("reason"))], wave2, consolidations)
    doc = {
        "schema": 1,
        "stage": "hng2-live-audit-sample",
        "items": audit,
        "review_values": ["correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "bad_llm_resolution", "uncertain", "not_reviewed"],
        "canonical_write_back": False,
        "offline_rebuild": True,
    }
    write_json(OUT / "audit-sample.json", doc)
    metrics_path = OUT / "metrics.json"
    if metrics_path.is_file():
        metrics = read_json(metrics_path, {})
        traces = read_json(OUT / "retrieval-trace.json", {}).get("records", [])
        evidence = {}
        for trace in traces:
            for ref, form in (trace.get("source_form_by_ref") or {}).items():
                evidence[str(ref)] = str(form)
        opened = collections.Counter(str(form) for trace in traces for form in (trace.get("source_form_by_ref") or {}).values())
        used = collections.Counter(str((trace.get("source_form_by_ref") or {}).get(str(ref))) for trace in traces for ref in trace.get("used_refs", []) if str(ref) in (trace.get("source_form_by_ref") or {}))
        retrieval = dict(metrics.get("retrieval") or {})
        retrieval["opened_source_form_distribution"] = dict(sorted(opened.items()))
        retrieval["used_source_form_distribution"] = dict(sorted(used.items()))
        retrieval["accepted_evidence_source_form_distribution"] = dict(sorted(collections.Counter(evidence.values()).items()))
        metrics["retrieval"] = retrieval
        attempts = []
        preflight_path = Path("/tmp/hng2-live-preflight.json")
        if preflight_path.is_file():
            attempts.extend(read_json(preflight_path, {}).get("attempts", []))
        for item in read_json(OUT / "manifest.json", {}).get("raw_extractions", []):
            raw_path = ROOT / str(item.get("path") or "")
            if raw_path.is_file():
                attempts.extend(read_json(raw_path, {}).get("attempts", []))
        model = dict(metrics.get("model") or {})
        model["transport_request_count"] = len(attempts)
        model["transport_retry_count"] = sum(int(row.get("attempt") or 1) > 1 for row in attempts)
        model["transport_success_count"] = sum(not row.get("failure_class") for row in attempts)
        metrics["model"] = model
        answers = dict(metrics.get("evaluation_answers") or {})
        answers["llm_validation_exercised"] = bool(model.get("identity_assist_calls"))
        metrics["evaluation_answers"] = answers
        metrics["offline_report_rebuild"] = True
        write_json(metrics_path, metrics)
        manifest_path = OUT / "manifest.json"
        manifest = read_json(manifest_path, {})
        if preflight_path.is_file():
            manifest["preflight"] = read_json(preflight_path, {})
            write_json(manifest_path, manifest)
    relations = read_json(OUT / "relations.json", {}).get("relations", [])
    temporal = read_json(OUT / "temporal-items.json", {}).get("temporal_items", [])
    _write_review(relations, temporal, audit)
    return {"audit_items": len(audit), "deterministic": sum(row.get("kind") == "identity" and row.get("resolution_method") in {"exact_name", "alias", "courtesy_name", "title", "decorated_name_suffix", "kinship_context", "reviewed_contextual_alias", "contextual_short_name", "biography_local_context"} for row in audit), "wave2": sum(row.get("kind") == "wave_2_promotion" for row in audit)}


if __name__ == "__main__":
    print(rebuild())
