#!/usr/bin/env python3
"""Validate HDB2-P1.1 occurrence-level candidate artifacts."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_occurrence_common as common  # noqa: E402


LOCAL_KEY = re.compile(r"^c\d+$")
FORBIDDEN_KEYS = common.FORBIDDEN_PROMPT_KEYS | {"person_id", "provisional_person_id", "graph_id", "relation_id"}
FORBIDDEN_PROMPT_VALUE = re.compile(r"\bperson-\d+\b")
VALID_STATUSES = {"explicit_resolved", "contextually_resolved", "contextually_preferred", "unresolved", "compositional_reference", "not_person"}


def walk(value: Any, path: str = "") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            found.append(("key", key_path, key))
            found.extend(walk(child, key_path))
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
    proposed_selection = common.build_selection(cases_doc)
    if selection != proposed_selection:
        errors.append("selection_not_immutable_or_projection_changed")
    if selection.get("occurrence_count") != 25:
        errors.append("unexpected_occurrence_count")
    selected_cases = [str(x.get("occurrence_id")) for x in selection.get("cases", [])]
    if len(selected_cases) != len(set(selected_cases)):
        errors.append("duplicate_occurrence_id")
    if not selection.get("frozen_before_live"):
        errors.append("selection_not_frozen")
    if selection.get("canonical_write_back") is not False:
        errors.append("selection_canonical_write_back")
    surfaces = {str(x.get("target_surface")) for x in selection.get("cases", [])}
    missing = sorted(set(common.REQUIRED_SURFACES) - surfaces)
    if missing:
        errors.append("required_surface_missing:" + ",".join(missing))

    cases_by_id = {str(x.get("occurrence_id")): x for x in cases_doc.get("cases", [])}
    for occurrence_id in selected_cases:
        case = cases_by_id.get(occurrence_id)
        if not case:
            errors.append(f"case_missing:{occurrence_id}")
            continue
        keys = [str(x) for x in case.get("candidate_keys", [])]
        if any(not LOCAL_KEY.fullmatch(key) for key in keys):
            errors.append(f"candidate_key_not_local:{occurrence_id}")
        for evidence in case.get("evidence_items", []):
            if not evidence.get("evidence_id") or not evidence.get("source_ref") or not evidence.get("text"):
                errors.append(f"evidence_item_incomplete:{occurrence_id}")
        span = str(case.get("exact_span") or "")
        if span and not any(span in str(item.get("text") or "") for item in case.get("evidence_items", [])):
            errors.append(f"occurrence_span_not_grounded:{occurrence_id}")

    prompts = common.read_json(run_dir / "prompts.json", {}) or {}
    prompt_records = prompts.get("records", [])
    if len(prompt_records) != len(selected_cases):
        errors.append("prompt_record_count")
    for row in prompt_records:
        for kind, path, value in walk(row.get("request")):
            if kind == "key" and value in FORBIDDEN_KEYS:
                errors.append(f"forbidden_prompt_key:{path}")
            if kind == "string" and FORBIDDEN_PROMPT_VALUE.search(value):
                errors.append(f"production_person_id_in_prompt:{path}")
        request = row.get("request") or {}
        if not isinstance(request, Mapping):
            errors.append("request_not_object")
        else:
            if request.get("tool_choice") != common.tool_choice():
                errors.append("tool_choice_not_forced")
            if len(request.get("tools", [])) != 1 or request.get("tools", [{}])[0] != common.strict_tool():
                errors.append("strict_tool_mismatch")

    model_doc = common.read_json(run_dir / "model-decisions.json", {}) or {}
    python_doc = common.read_json(run_dir / "python-decisions.json", {}) or {}
    model_records = list(model_doc.get("records", []))
    python_records = list(python_doc.get("records", []))
    if len(model_records) != len(selected_cases) or len(python_records) != len(selected_cases):
        errors.append("decision_record_count")
    by_seq = {int(x.get("sequence")): x for x in model_records if str(x.get("sequence", "")).isdigit()}
    by_py_seq = {int(x.get("sequence")): x for x in python_records if str(x.get("sequence", "")).isdigit()}
    replay_differences: list[str] = []
    for sequence, occurrence_id in enumerate(selected_cases, start=1):
        case = cases_by_id.get(occurrence_id)
        if not case:
            continue
        model = by_seq.get(sequence, {})
        payload = model.get("payload", {})
        if not isinstance(payload, Mapping):
            payload = {}
        validation = common.validate_model_payload(payload, case)
        stored_validation = model.get("validation", {})
        if model.get("classification") == "parsed" and bool(validation.get("valid")) != bool(stored_validation.get("valid")):
            replay_differences.append(f"validation:{sequence}")
        replay = common.python_decision(case, payload, validation)
        stored = by_py_seq.get(sequence, {})
        stable_fields = ("status", "candidate_key", "resolved_person_id", "support_families", "hard_constraint_rejections")
        if any(replay.get(field) != stored.get(field) for field in stable_fields):
            replay_differences.append(f"decision:{sequence}")
        if stored.get("status") not in VALID_STATUSES:
            errors.append(f"invalid_final_status:{sequence}")
        if stored.get("status") == "compositional_reference" and stored.get("resolved_person_id"):
            errors.append(f"compositional_base_person_resolved:{sequence}")
        if stored.get("status") in {"explicit_resolved", "contextually_resolved"}:
            key = stored.get("candidate_key")
            if key not in case.get("candidate_keys", []):
                errors.append(f"resolved_key_outside_case:{sequence}")
    if replay_differences:
        errors.extend("deterministic_replay:" + item for item in replay_differences)

    raw_dir = run_dir / "raw-api"
    if not raw_dir.is_dir():
        errors.append("raw_api_missing")
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    for relative, expected in (manifest.get("protected_hashes_before") or {}).items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            errors.append(f"protected_hash_changed:{relative}")
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        errors.append("protected_hash_before_after_mismatch")
    for relative, expected in (manifest.get("raw_api_hashes") or {}).items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            errors.append(f"raw_api_hash_changed:{relative}")
    if manifest.get("canonical_write_back") is not False:
        errors.append("manifest_canonical_write_back")
    if manifest.get("retrieval_calls") != 0 or manifest.get("search_calls") != 0:
        errors.append("unexpected_retrieval_or_search")
    if model_doc.get("canonical_write_back") is not False or python_doc.get("canonical_write_back") is not False:
        errors.append("decision_canonical_write_back")

    result = {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "occurrence_count": len(selected_cases),
        "deterministic_replay": not replay_differences,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json")
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p1-1-occurrence-cases.json")
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    result = validate_run(run_dir, selection_path=args.selection, cases_path=args.cases)
    print(__import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
