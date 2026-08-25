#!/usr/bin/env python3
"""Validate HDB2-P2T selection, cascade safety, and deterministic replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_occurrence_common as occurrence  # noqa: E402
import hdb2_p2t_common as common  # noqa: E402


LOCAL_KEY = re.compile(r"^c\d+$")
FORBIDDEN_KEYS = {"person_id", "provisional_person_id", "graph_id", "priority_score", "surface_cluster_decision", "canonical_graph_action"}
FORBIDDEN_PERSON_ID = re.compile(r"\bperson-\d+\b")


def walk(value: Any, path: str = "") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            found.append(("key", current, key))
            found.extend(walk(child, current))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(walk(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append(("string", path, value))
    return found


def validate_run(run_dir: Path, *, selection_path: Path, cases_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    selection = common.read_json(selection_path, {}) or {}
    cases_doc = common.read_json(cases_path, {}) or {}
    if selection != common.build_selection(cases_doc):
        errors.append("selection_not_frozen")
    if selection.get("occurrence_count") != 40:
        errors.append("selection_count_not_40")
    p11 = common.read_json(common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json", {}) or {}
    p11_ids = {str(row.get("identity_observation_id")) for row in p11.get("cases", [])}
    selected_ids = {str(row.get("identity_observation_id")) for row in selection.get("cases", [])}
    if not selected_ids.isdisjoint(p11_ids):
        errors.append("p1_1_occurrence_overlap")
    if len(selected_ids) != 40:
        errors.append("selection_identity_observation_duplicates")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("selection_candidate_invariant")

    cases_by_id = {str(row.get("occurrence_id")): row for row in cases_doc.get("cases", [])}
    selected_order = [str(row.get("occurrence_id")) for row in selection.get("cases", [])]
    if len(selected_order) != len(set(selected_order)):
        errors.append("duplicate_occurrence_ids")
    for occurrence_id in selected_order:
        case = cases_by_id.get(occurrence_id)
        if not case:
            errors.append(f"missing_case:{occurrence_id}")
            continue
        keys = [str(row.get("candidate_key")) for row in case.get("candidates", [])]
        if any(not LOCAL_KEY.fullmatch(key) for key in keys):
            errors.append(f"nonlocal_candidate_key:{occurrence_id}")
        for item in case.get("evidence_items", []):
            if not item.get("evidence_id") or not item.get("source_ref") or not item.get("text"):
                errors.append(f"incomplete_evidence_item:{occurrence_id}")
        if case.get("exact_span") and not any(str(case["exact_span"]) in str(item.get("text") or "") for item in case.get("evidence_items", [])):
            errors.append(f"occurrence_exact_span_not_grounded:{occurrence_id}")

    packets = common.read_json(run_dir / "prompt-packets.json", {}) or {}
    packet_records = packets.get("records", [])
    if len(packet_records) != 40:
        errors.append("packet_record_count")
    for packet in packet_records:
        request = packet.get("request")
        if not packet.get("llm_called"):
            if request is not None:
                errors.append("python_case_has_prompt")
            continue
        for kind, path, value in walk(request):
            if kind == "key" and value in FORBIDDEN_KEYS:
                errors.append(f"forbidden_prompt_key:{path}")
            if kind == "string" and FORBIDDEN_PERSON_ID.search(value):
                errors.append(f"person_id_in_prompt:{path}")
        if not isinstance(request, Mapping) or request.get("tool_choice") != occurrence.tool_choice() or request.get("tools") != [occurrence.strict_tool()]:
            errors.append("strict_tool_not_frozen")

    model_doc = common.read_json(run_dir / "model-decisions.json", {}) or {}
    py_doc = common.read_json(run_dir / "python-decisions.json", {}) or {}
    model_records = list(model_doc.get("records", []))
    python_records = list(py_doc.get("records", []))
    if len(model_records) != 40 or len(python_records) != 40:
        errors.append("decision_record_count")
    model_by_seq = {int(row.get("sequence")): row for row in model_records if str(row.get("sequence", "")).isdigit()}
    py_by_seq = {int(row.get("sequence")): row for row in python_records if str(row.get("sequence", "")).isdigit()}
    replay_diffs: list[str] = []
    allowed = common.FINAL_STATUSES
    for sequence, occurrence_id in enumerate(selected_order, start=1):
        case = cases_by_id.get(occurrence_id)
        if not case:
            continue
        model = model_by_seq.get(sequence, {})
        stored = py_by_seq.get(sequence, {})
        if model.get("llm_called"):
            payload = model.get("payload") if isinstance(model.get("payload"), Mapping) else {}
            if model.get("classification") == "parsed":
                validation = occurrence.validate_model_payload(payload, case)
            else:
                validation = model.get("validation") or {"valid": False, "errors": [str(model.get("classification"))], "payload": {}}
            replay = common.apply_llm_result(case, payload, validation)
        else:
            replay = common.deterministic_cascade(case)
            replay["identity_observation_id"] = case.get("identity_observation_id")
        for field in ("status", "candidate_key", "resolved_person_id", "cascade_stage", "llm_called", "hard_constraint_rejections"):
            if replay.get(field) != stored.get(field):
                replay_diffs.append(f"{sequence}:{field}")
        if stored.get("status") not in allowed:
            errors.append(f"invalid_final_status:{sequence}")
        if stored.get("status") == "compositional_reference" and stored.get("resolved_person_id"):
            errors.append(f"base_person_compositional_collapse:{sequence}")
        if str(case.get("occurrence_type")) == "generic_or_non_person_reference" and stored.get("resolved_person_id"):
            errors.append(f"nonperson_person_id:{sequence}")
        if stored.get("status") in {"explicit_resolved", "contextually_resolved"} and stored.get("candidate_key") not in case.get("candidate_keys", []):
            errors.append(f"resolved_candidate_not_in_case:{sequence}")
    errors.extend("deterministic_replay:" + value for value in replay_diffs)

    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        errors.append("manifest_candidate_invariant")
    if manifest.get("new_retrieval_calls") != 0 or manifest.get("search_plan_calls") != 0:
        errors.append("new_retrieval_or_search")
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        errors.append("protected_hash_mismatch")
    for relative, expected in (manifest.get("protected_hashes_before") or {}).items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            errors.append(f"protected_file_changed:{relative}")
    for relative, expected in (manifest.get("raw_api_hashes") or {}).items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            errors.append(f"raw_response_changed:{relative}")
    metrics = common.read_json(run_dir / "metrics.json", {}) or {}
    safety = metrics.get("safety", {})
    for key in ("known_wrong_identity_promotions", "base_person_compositional_collapses", "nonperson_person_id_anomalies", "self_relation_collapses", "same_surface_automatic_merges"):
        if safety.get(key, 0) != 0:
            errors.append(f"safety_gate:{key}")

    result = {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "occurrence_count": len(selected_order),
        "deterministic_replay": not replay_diffs,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p2t-occurrence-selection.json")
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p2t-occurrence-cases.json")
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    result = validate_run(run_dir, selection_path=args.selection, cases_path=args.cases)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
