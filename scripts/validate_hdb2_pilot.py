#!/usr/bin/env python3
"""Validate HDB2-P1 candidate-only boundaries and deterministic replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
import solve_hdb2_constraints as solver  # noqa: E402
from hdb2_p1_common import ANNOTATION, stable_hash, read_json  # noqa: E402

FORBIDDEN_KEYS = {"person_id", "provisional_person_id", "candidate_id", "candidate_key", "relation_id", "graph_id"}
PRODUCTION_PERSON = re.compile(r"^person-[0-9]+$")
BASIS_VALUES = {"catalogue_exact_match", "evidence_identity_assertion", "contextual_name_projection", "new_candidate", "unresolved"}


def _walk_keys(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            out.append(str(key)); out.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value: out.extend(_walk_keys(child))
    return out


def _check_selection(path: Path) -> list[str]:
    errors: list[str] = []
    selection = read_json(path, {}) or {}
    cases = list(selection.get("cases", []))
    if selection.get("selected_case_count") != 24 or len(cases) != 24: errors.append("selection_count_not_24")
    if not selection.get("frozen_before_live"): errors.append("selection_not_frozen")
    if selection.get("canonical_write_back") is not False: errors.append("selection_canonical_write")
    if selection.get("selection_hash") != stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}): errors.append("selection_hash_invalid")
    if len({str(x.get("candidate_identity_id")) for x in cases}) != 24: errors.append("selection_clusters_not_unique")
    if any(str(x.get("current_status")) != "unresolved_surface_cluster" for x in cases): errors.append("selection_contains_non_unresolved_cluster")
    return errors


def _check_atoms(case_results: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for case in case_results:
        for round_row in case.get("rounds", []):
            validation = round_row.get("validation") or {}
            passages = {str(x.get("ref")): str(x.get("evidence_text") or "") for x in (round_row.get("search") or {}).get("selected_passages", [])}
            for atom in validation.get("valid_atoms", []):
                ref = str(atom.get("evidence_ref") or ""); span = str(atom.get("exact_span") or "")
                if ref not in passages or not span or span not in passages[ref]: errors.append(f"invalid_grounding:{case.get('case_id')}:{atom.get('atom_id')}")
                for field in ("subject_surface", "predicate_surface", "object_surface", "temporal_surface"):
                    if str(atom.get(field) or "") and str(atom.get(field)) not in span: errors.append(f"invalid_surface_grounding:{case.get('case_id')}:{atom.get('atom_id')}:{field}")
            request_user = ((round_row.get("transport") or {}).get("request") or {}).get("user") or {}
            if set(request_user) != {"task", "target_surfaces", "source_passages"}: errors.append(f"non_candidate_blind_request:{case.get('case_id')}")
            if any(key in _walk_keys(request_user) for key in FORBIDDEN_KEYS): errors.append(f"forbidden_prompt_key:{case.get('case_id')}")
    return errors


def _check_decisions(solved: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    catalog_ids = set(hng02.person_catalog())
    valid = {"resolved_existing", "resolved_new_candidate", "narrowed", "unresolved", "conflict"}
    for row in solved.get("cases", []):
        decision = row.get("decision", {})
        if decision.get("status") not in valid: errors.append(f"invalid_decision:{row.get('case_id')}")
        if decision.get("status") == "resolved_existing" and not decision.get("identity_support"):
            errors.append(f"identity_resolution_without_explicit_support:{row.get('case_id')}")
        pid = str(decision.get("resolved_person_id") or "")
        if pid and pid not in catalog_ids: errors.append(f"unknown_person_id:{row.get('case_id')}:{pid}")
        if decision.get("status") == "resolved_new_candidate" and pid: errors.append(f"new_candidate_has_person_id:{row.get('case_id')}")
        basis = str(decision.get("identity_resolution_basis") or "")
        if basis not in BASIS_VALUES: errors.append(f"invalid_identity_resolution_basis:{row.get('case_id')}:{basis}")
        for support in decision.get("identity_support", []):
            if str(support.get("basis") or "") not in {"evidence_identity_assertion", "contextual_name_projection"}:
                errors.append(f"invalid_identity_support_basis:{row.get('case_id')}:{support.get('basis')}")
        if row.get("canonical_write_back") is not False: errors.append(f"case_canonical_write:{row.get('case_id')}")
        for relation in row.get("newly_unblocked_candidate_facts", []):
            if relation.get("canonical_write_back") is not False: errors.append(f"unblocked_canonical_write:{relation.get('candidate_id')}")
            if str(relation.get("resolved_person_id")) == str(relation.get("other_person_id")):
                errors.append(f"collapsed_self_relation_survived:{relation.get('candidate_id')}")
    return errors


def validate(run_dir: Path, selection_path: Path = ANNOTATION / "hdb2-p1-selection.json") -> dict[str, Any]:
    run_dir = run_dir.resolve()
    selection_path = selection_path.resolve()
    errors = _check_selection(selection_path)
    selection = read_json(selection_path, {}) or {}
    live = read_json(run_dir / "case-results.json", {}) or {}
    case_results = list(live.get("cases", []))
    if len(case_results) != 24: errors.append("live_case_count_not_24")
    errors.extend(_check_atoms(case_results))
    solved = read_json(run_dir / "constraint-results.json", {}) or {}
    errors.extend(_check_decisions(solved))
    manifest = read_json(run_dir / "manifest.json", {}) or {}
    if manifest.get("selection_hash") != selection.get("selection_hash"): errors.append("run_selection_hash_mismatch")
    if manifest.get("canonical_write_back") is not False: errors.append("manifest_canonical_write")
    for path, expected in (manifest.get("protected_hashes_before_live") or {}).items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest() if (ROOT / path).is_file() else None
        if actual != expected: errors.append(f"protected_hash_changed:{path}")
    for path, expected in (manifest.get("raw_api_hashes") or {}).items():
        actual_path = run_dir / path
        actual = hashlib.sha256(actual_path.read_bytes()).hexdigest() if actual_path.is_file() else None
        if actual != expected: errors.append(f"raw_api_hash_changed:{path}")
    # Replay must be deterministic without calling the provider.
    replay_a = solver.solve_run(run_dir, selection)
    replay_b = solver.solve_run(run_dir, selection)
    if stable_hash(replay_a) != stable_hash(replay_b): errors.append("non_deterministic_solver_replay")
    forbidden_raw = []
    for path in sorted((run_dir / "raw-api").glob("*.json")):
        doc = read_json(path, {})
        if any(key in FORBIDDEN_KEYS for key in _walk_keys(doc)): forbidden_raw.append(str(path.relative_to(ROOT)))
    if forbidden_raw: errors.append("model_emitted_forbidden_id_key")
    return {"schema": "hdb2-p1-validation-v1", "run_dir": str(run_dir.relative_to(ROOT)), "passed": not errors, "errors": sorted(set(errors)), "case_count": len(case_results), "canonical_write_back": False, "api_calls_not_replayed": True}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("run_dir", type=Path); parser.add_argument("--selection", type=Path, default=ANNOTATION / "hdb2-p1-selection.json")
    args = parser.parse_args(); result = validate(args.run_dir, args.selection); print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)); return 0 if result["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
